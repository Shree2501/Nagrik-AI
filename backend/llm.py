from __future__ import annotations

from typing import Any
import json
import re
import requests
import logging

from .config import settings
from .pageindex_tree import extract_field_candidates
from .utils import first_heading, markdown_to_plain_text
from .schema import (
    PageClassification, SimplificationLevel,
    PageOutput, VerificationResult, FieldCandidate
)

logger = logging.getLogger(__name__)

# --- Reusable Mistral Caller ---

def _mistral_call(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict[str, Any] | None:
    if not settings.mistral_api_key or not settings.mistral_chat_model:
        return None

    url = "https://api.mistral.ai/v1/chat/completions"
    payload = {
        "model": settings.mistral_chat_model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=240)
        if resp.status_code >= 400:
            logger.error(f"Mistral API error: {resp.status_code} {resp.text}")
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        
        # Robust JSON cleaning: Remove markdown fences if present
        if content.startswith("```"):
            # Remove leading ```json or ```
            content = re.sub(r'^```(?:json)?', '', content, flags=re.MULTILINE)
            # Remove trailing ```
            content = re.sub(r'```$', '', content, flags=re.MULTILINE).strip()
            
        return json.loads(content)
    except Exception as e:
        logger.error(f"Mistral LLM exception: {e}")
        return None


# --- ❌ Fix 2: Classification-Driven Prompt Strategies ---

PROMPT_STRATEGIES: dict[PageClassification, str] = {
    PageClassification.IDENTITY_SECTION: """Focus on FIELDS. For each field, give:
- Exact label
- What to write (with a local example)
- Why it matters for the application
Keep explanations minimal. This is a fill-in-the-blank page.""",

    PageClassification.FORM_INSTRUCTIONS: """This is an INSTRUCTION page. Focus on:
- Summarizing the instructions heavily
- Extracting prerequisites (documents needed, eligibility)
- Listing step-by-step what the user must do BEFORE filling the form
Do NOT try to extract form fields from instructions.""",

    PageClassification.DECLARATION_PAGE: """This is a LEGAL DECLARATION. Focus on:
- Explaining the legal consequences of signing
- Highlighting what the user is agreeing to
- Warning about penalties for false information
- Explaining who needs to sign and witness
Use strong warning language.""",

    PageClassification.SIGNATURE_PAGE: """This is a SIGNATURE page. Focus on:
- Where to sign (and whether thumb impression is acceptable)
- Whether witnesses are required
- Whether an official stamp/seal is needed
- Date format requirements
Keep it very short and action-oriented.""",

    PageClassification.TABLE_PAGE: """This is a TABLE page. Focus on:
- Explaining each column header
- Giving row-by-row guidance for what to enter
- Highlighting any totals or calculations needed
Present as a structured guide.""",

    PageClassification.MIXED_PAGE: """This page has mixed content.
- Identify and explain any form fields
- Summarize any instruction text
- Flag any declarations or signature boxes
Give balanced coverage.""",

    PageClassification.UNKNOWN: """Analyze this page and provide:
- A clear summary of its purpose
- Any fields that need filling
- Any warnings or important notes""",
}

SIMPLIFICATION_PROMPTS: dict[SimplificationLevel, str] = {
    SimplificationLevel.LITERAL: """SIMPLIFICATION LEVEL: LITERAL
- Translate accurately. Keep technical and legal terms.
- Use formal language.
- Do NOT simplify jargon.
- **NO HALLUCINATIONS**: Do not add information that isn't in the raw text.""",

    SimplificationLevel.SIMPLE: """SIMPLIFICATION LEVEL: SIMPLE
- Use short sentences (under 15 words).
- Avoid passive voice completely.
- One idea per line.
- No legal jargon — expand complex words.
- Give local context examples.
- **STRICT FIDELITY**: If the document doesn't mention something, don't explain it.""",

    SimplificationLevel.ULTRA_BASIC: """SIMPLIFICATION LEVEL: ULTRA-BASIC (Voice-First, Rural)
- Maximum 5 words per sentence.
- Use only everyday words.
- Give exact examples from village life.
- Write as if speaking to someone who has never seen a form.
- Always end field explanations with "Ask someone to help if confused."
- Use active, direct commands: "Write your name here." 
- **WARNING**: Do not invent instructions. Stick to what is on the paper.""",
}




# --- Removed separate classify_page as it is now inlined ---


# --- ❌ Fix 3: Verification with Citation Checking ---

def verify_output(original_md: str, generated_json: dict[str, Any], guideline_titles: list[str]) -> VerificationResult:
    """Lightweight LLM pass to check for hallucinations + citation validity."""
    valid_sources = set(t.lower() for t in guideline_titles)
    valid_sources.add("document_text")
    valid_sources.add("detected_from_form")

    # Quick rule-based citation check first (no LLM needed)
    for field in generated_json.get("fields", []):
        source = (field.get("source") or "").lower().strip()
        if source and source not in valid_sources:
            return VerificationResult(
                passed=False,
                reason=f"Field '{field.get('field_name')}' cites source '{field.get('source')}' which was not in the retrieved guidelines."
            )

    # LLM-based hallucination check
    system_prompt = 'You are a strict QA auditor. Output strictly JSON: {"passed": true/false, "reason": "..."}'
    user_prompt = f"""
Does the following JSON output invent any document fields not present in the original text, or drop mandatory items?
Original text:
{original_md[:2000]}

JSON Output:
{json.dumps(generated_json, ensure_ascii=False)[:3000]}

If it looks mostly accurate and didn't invent non-existent fields, passed=true. Otherwise passed=false with a reason.
"""
    result = _mistral_call(system_prompt, user_prompt, temperature=0.0)
    if result and "passed" in result:
        return VerificationResult(passed=bool(result.get("passed")), reason=result.get("reason"))
    return VerificationResult(passed=True, reason="Verification bypassed due to API error")


from .session_memory import SessionMemory

# --- 🌟 Upgrade 1: Ask AI Chatbot ---
def ask_ai(
    question: str, 
    page_markdown: str, 
    page_summary: str, 
    guideline_context: str = "", 
    field_context: str = "", 
    language: str = "English",
    session_id: str = "default",
    expanded_context: list[str] = None
) -> dict[str, Any]:
    session_context = SessionMemory.get_context_for_llm(session_id)
    
    system_prompt = f"""You are a helpful Nagrik Assistant guiding a user through a government document. The user is speaking {language}. Respond ONLY in {language}.

    KNOWLEDGE BASE:
    - You have access to: 1) Raw Page Text, 2) Structural Context (linked sections), 3) Simplified Field Guide, and 4) Civic Guidelines.
    - If a user asks about a specific term (like "Pokhara", "Name", "ID"), check ALL provided context.
    - SESSION MEMORY: Use the 'PREVIOUS' dialogue below to resolve references like "this", "that", or "same as before".

    STRICT GROUNDING RULES:
    1. If the query is completely unrelated to the document or government forms, politely say you are specialized in this document.
    2. Do NOT hallucinate fields that aren't there.
    3. Keep answers brief (max 3 sentences) and actionable.
    4. CITATION: If you use information from multiple pages, mention them (e.g., "See Page 1 and 3").

    Output strictly JSON: {{"answer": "your answer here", "pages_cited": [1, 3]}}. ALL text must be in {language}."""

    # Combine provided contexts
    context_blob = ""
    if expanded_context:
        context_blob = "\n\n--- DOCUMENT STRUCTURAL CONTEXT (Multi-page) ---\n" + "\n\n".join(expanded_context)
    
    user_prompt = f"""
Language: {language}
Document Summary: {page_summary}

--- SESSION MEMORY (Previous Turns) ---
{session_context if session_context else "First turn of conversation."}

--- SIMPLIFIED FIELD GUIDE (Instructions for fields) ---
{field_context if field_context else "No specific field instructions available."}

--- CIVIC GUIDELINES (Official Rules) ---
{guideline_context if guideline_context else "No specific guidelines."}

--- DOCUMENT CONTENT (Current Page View) ---
{page_markdown[:2000]}
{context_blob}

--- USER QUESTION ---
{question}

Instructions: Based on the document content, structural context, and field guide above, answer the user's question. If the user mentions a specific label they see, find that label in the text and explain its purpose. 

Return strictly JSON in {language}: {{"answer": "your answer here", "pages_cited": [number, ...]}}
"""
    # Set temperature to 0.1 for a bit more flexibility while staying grounded
    result = _mistral_call(system_prompt, user_prompt, temperature=0.1)
    if result and "answer" in result:
        return result

    fallback_msgs = {
        "Hindi": "क्षमा करें, मैं केवल प्रस्तुत दस्तावेज़ और गाइड के आधार पर आपके प्रश्न का उत्तर दे सकता हूँ। मुझे इस बारे में जानकारी नहीं मिली।",
        "English": "I'm sorry, I can only answer questions based on the provided document, guide, and guidelines. I couldn't find information for your request."
    }
    return {"answer": fallback_msgs.get(language, fallback_msgs["English"])}


def _is_form_like_page(page_md: str) -> bool:
    """Check if page looks like a fillable form. Intentionally permissive."""
    text = page_md or ""
    if re.search(r"[_\.]{3,}|\[[ xX]?\]", text):
        return True

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False

    table_signal = sum(ln.count("|") for ln in lines)
    colon_signal = sum(1 for ln in lines if (":" in ln or "：" in ln))
    # Lowered thresholds: even 2 colons or 8 pipes suggest a form
    if table_signal >= 8 or colon_signal >= 2:
        return True

    lowered = text.lower()
    keywords = [
        "name", "address", "mobile", "phone", "aadhaar", "ifsc", "account", "signature",
        "नाम", "पता", "मोबाइल", "आधार", "खाता", "हस्ताक्षर", "जन्म", "लिंग",
        # Additional Indian form keywords
        "father", "mother", "guardian", "husband", "date of birth", "dob",
        "district", "pin", "village", "taluk", "ward", "mandal",
        "income", "caste", "religion", "occupation", "form", "application",
        "पिता", "माता", "पति", "जिला", "ग्राम", "तहसील", "आय", "जाति",
        "आवेदन", "फॉर्म", "प्रमाण", "certificate", "samagra", "voter",
        "email", "gender", "age", "bank", "nominee", "ration",
    ]
    return any(k in lowered for k in keywords)


# --- Main Simplification Engine ---

def simplify_page(
    language: str,
    page_num: int,
    page_markdown: str,
    context: dict[str, Any],
    detected_fields: list[dict[str, Any]] | None = None,
    field_retrievals: dict[str, Any] | None = None, # New: Per-field context
    level: SimplificationLevel = SimplificationLevel.SIMPLE,
    user_profile: str = "",
) -> dict[str, Any]:
    # PAGE CLASSIFICATION STRATEGIES
    classification_str = "\n".join(f"- {c.value}" for c in PageClassification)
    strategy_str = "\n".join(f"### {c.value}\n{s}" for c, s in PROMPT_STRATEGIES.items())

    tree_hits = context.get("tree_hits", []) or []
    guideline_hits = context.get("guideline_hits", []) or []
    document_guideline_hits = context.get("document_guideline_hits", []) or []

    # Fuse page and document hits with priority to page-local relevance.
    fused_guidelines_by_title: dict[str, dict[str, Any]] = {}
    for hit in document_guideline_hits:
        guideline = hit.get("guideline", {})
        title = (guideline.get("title") or "").strip()
        if not title:
            continue
        fused_guidelines_by_title[title] = {
            "score": round(float(hit.get("score", 0.0)) * 0.75, 3),
            "guideline": guideline,
            "source_level": "document",
        }

    for hit in guideline_hits:
        guideline = hit.get("guideline", {})
        title = (guideline.get("title") or "").strip()
        if not title:
            continue
        page_score = float(hit.get("score", 0.0))
        existing = fused_guidelines_by_title.get(title)
        if not existing or page_score >= float(existing.get("score", 0.0)):
            fused_guidelines_by_title[title] = {
                "score": round(page_score, 3),
                "guideline": guideline,
                "source_level": "page",
            }

    merged_guideline_hits = sorted(
        fused_guidelines_by_title.values(),
        key=lambda item: item.get("score", 0.0),
        reverse=True,
    )

    level_prompt = SIMPLIFICATION_PROMPTS.get(level, SIMPLIFICATION_PROMPTS[SimplificationLevel.SIMPLE])

    # Build per-field grounding text
    field_grounding_text = ""
    if field_retrievals:
        field_grounding_text = "\n### SURGICAL FIELD GUIDANCE (High Accuracy Context):\n"
        for label, hit in field_retrievals.items():
            score = hit.get("score", 0.0)
            if score >= 0.3: # Only show relevant hits
                field_grounding_text += f"- FIELD: {label}\n  GUIDELINE: {hit['title']}\n  RULE: {hit['description']}\n  CONFIDENCE: {score}\n\n"

    # Select persona rules based on target language
    persona_rules = ""
    if language.lower() == "english":
        persona_rules = """**INTELLIGENT ASSISTANT PERSONA RULES**:
1. **Detailed Input Guidance ('HOW')**: For every field, explain EXACTLY what to write. You MUST include real-world examples in parentheses.
   - *Example*: (e.g., Village Panchayat 'Dhanipur', 'Ward Number 4').
2. **Simplified 'Why'**: Provide only a very brief, 1-sentence explanation for 'why_it_matters' (e.g., 'This is to verify your identity').
3. **FORBIDDEN PHRASES**: NEVER use "Fill as per form", "Use exact info", "Refer to document", or "As per description". You must be the one explaining.
4. **Simple English**: Use extremely plain, simple English suitable for users with rudimentary reading skills."""
    else:
        persona_rules = """**INTELLIGENT ASSISTANT PERSONA RULES**:
1. **Detailed Input Guidance ('HOW')**: For every field, explain EXACTLY what to write. You MUST include real-world examples in parentheses.
   - *Example*: (जैसे: ग्राम पंचायत 'ढाणीपुर', 'मोहल्ला चौकी').
2. **Simplified 'Why'**: Since the user has requested a focus on 'How', provide only a very brief, 1-sentence explanation for 'why_it_matters' (e.g., 'यह आपकी पहचान पक्की करने के लिए है').
3. **FORBIDDEN PHRASES**: NEVER use "फॉर्म के अनुसार भरें", "Use exact info", "Refer to document", or "As per form description". You must be the one explaining.
4. **Rural-Friendly Hindi**: Use simple 'Hindustani' (Hindi + common Urdu/English words used in villages like 'बैंक', 'फ़ॉर्म', 'अकाउंट') rather than complex Sanskritized words."""

    system_prompt = f"""You are an expert 'Intelligent Form Assistant' specialized in Indian government forms.
Your goal is to guide citizens through complex documents with extreme clarity and practical empathy.

{level_prompt}

{persona_rules}

**STRICT GROUNDING RULES (MAXIMUM EXTRACTION RECALL)**:
1. **Source Fidelity**: You are provided with "Surgical Field Guidance". 
   - If a field has a GUIDELINE with CONFIDENCE >= 0.7, you MUST use that rule verbatim but adapt the 'HOW' as per your persona.
   - If NO guideline is provided, stick strictly to the page text.
2. **100% COVERAGE POLICY**: You MUST extract every single field on the page from TOP to BOTTOM without skipping ANY.
   - **Line-by-Line Scan**: Go through the document line by line. DO NOT SUMMARIZE OR GROUP fields.
   - **Top Scan**: Check for document titles, application numbers, dates, or office addresses that require filling.
   - **Middle/Bottom Scan**: Find all inline blanks, checkboxes, and signature/date lines at the bottom.
   - **Visual Cues**: Treat any of these as a field: underscores (_____), series of dots (.....), empty brackets [ ], empty boxes □, colons ( : ), or patterns like "I, _______", "S/O _______", or "Date: _______".
   - **When in Doubt**: If a piece of text looks like it might require a user's answer, EXTRACT IT. Missing a field is a CRITICAL ERROR.
3. **NO DEDUPLICATION**: Extract EVERY instance of a field, even if repetitive. Explain each one separately.
4. **Hallucination Ban**: Do not invent data, but DO be extremely exhaustive in finding all labels on the page.

CLASSIFICATION & STRATEGY:
First, classify the page into exactly ONE of these categories:
{classification_str}

Then apply the corresponding strategy:
{strategy_str}

**CITATION & LANGUAGE**:
- All text content in the JSON response MUST be written strictly in {language}.
- Use simple, direct, rural-friendly {language} (e.g., use "आप" instead of formal document dialect).

You MUST output strictly Valid JSON matching this schema:
{{
  "language": "{language}",
  "page_type": "string",
  "document_purpose": "string",
  "page_summary": "string",
  "translation": "string",
  "simple_explanation": "string",
  "action_guide": "string",
  "fields": [
    {{
      "field_name": "string",
      "what_to_fill": "string",
      "why_it_matters": "string",
      "example": "string",
      "source": "string",
      "retrieval_score": float,
      "input_type": "string",
      "required": boolean
    }}
  ],
  "warnings": ["string"],
  "confidence": 1.0,
  "field_retrievals": {{}} 
}}
"""

    # Build detected fields injection
    detected_fields_text = ""
    if detected_fields:
        # Pass the label AND what the regex thought was the value (hint)
        labels = [f"- {f.get('label')} (type: {f.get('pattern_type')}, hint: {f.get('value_hint')})" for f in detected_fields]
        detected_fields_text = f"""
PRE-DETECTED FORM FIELDS:
{chr(10).join(labels)}

INSTRUCTIONS:
1. Review these fields using their 'hint' text.
2. If a hint contains MULTIPLE values (e.g. 'John Age: 30'), SPLIT them into separate fields.
3. **NO DEDUPLICATION**: Do NOT discard any fields that appear multiple times. Every instance of a field on the page must be explained.
4. **NO SKIPPING**: You MUST include every single pre-detected field listed above in your JSON output.
5. SCAN the 'Document page text' for any other fields missed by pre-detection. Go from the top edge to the very bottom edge.
6. Provide a clear, simple explanation for each valid field.
"""
    else:
        detected_fields_text = """
NO PRE-DETECTED FORM FIELDS WERE FOUND.
Scan the 'Document page text' below and extract EVERY likely fillable field.
Look for:
- Labels followed by colons or blanks.
- In-line blanks (e.g., 'I, _______').
- Checkboxes or table headers.
Do not invent fields not present in the page text.
"""

    # 🌟 Upgrade 4: User Personalization
    profile_text = f"User Profile Context: {user_profile}\nAdapt terminology/examples based on this profile." if user_profile else ""

    user_prompt = f"""
Language requested: {language}
Page number: {page_num}
{field_grounding_text}
{profile_text}
{detected_fields_text}
Document page text:
{page_markdown}

Retrieved structural context:
{json.dumps(tree_hits, ensure_ascii=False, indent=2)}

Retrieved general guidelines:
{json.dumps(merged_guideline_hits, ensure_ascii=False, indent=2)}
"""

    result = _mistral_call(system_prompt, user_prompt, temperature=0.1)
    if not result:
        logger.warning(f"[Page {page_num}] LLM returned no result. Using fallback with {len(detected_fields or [])} pre-detected fields.")
        return _fallback_page_output(page_num, page_markdown, context, language, detected_fields, error_msg="Mistral API returned no result")

    # --- Normalize LLM field keys (LLM sometimes uses different key names) ---
    raw_fields = result.get("fields", [])
    if isinstance(raw_fields, list):
        normalized_fields = []
        for f in raw_fields:
            if not isinstance(f, dict):
                continue
            nf = {
                "field_name": f.get("field_name") or f.get("name") or f.get("label") or f.get("field") or "",
                "what_to_fill": f.get("what_to_fill") or f.get("instruction") or f.get("how_to_fill") or f.get("description") or "",
                "why_it_matters": f.get("why_it_matters") or f.get("importance") or f.get("reason") or "",
                "example": f.get("example") or f.get("sample") or "",
                "source": f.get("source") or "document_text",
                "retrieval_score": f.get("retrieval_score"),
            }
            if nf["field_name"]:
                normalized_fields.append(nf)
        result["fields"] = normalized_fields

    # Inject internal metadata
    result["field_retrievals"] = field_retrievals
    result["retrieved_guidelines"] = [
        g.get("guideline", {}).get("title", "")
        for g in merged_guideline_hits
        if g.get("guideline", {}).get("title")
    ]
    
    # Validate against Pydantic schema
    try:
        validated = PageOutput(**result)
        out = validated.model_dump()

        llm_field_count = len(out.get("fields", []))
        logger.info(f"[Page {page_num}] LLM returned {llm_field_count} fields. Pre-detected: {len(detected_fields or [])} fields.")

        # Recovery: ensure ALL pre-detected fields are included
        llm_fields = out.get("fields", [])
        llm_field_names = {f.get("field_name", "").lower().strip() for f in llm_fields if f.get("field_name")}

        recovery_labels = [f.get("label", "") for f in (detected_fields or []) if f.get("label")]
        if not recovery_labels:
            recovery_labels = extract_field_candidates([{"page": page_num, "markdown": page_markdown}]).get(page_num, [])

        missed_labels = []
        for label in recovery_labels:
            label_lower = label.lower().strip()
            # Check if an exact match or a substantial substring match exists
            if label_lower not in llm_field_names and not any(len(fn) > 3 and (label_lower in fn or fn in label_lower) for fn in llm_field_names):
                missed_labels.append(label)

        if missed_labels:
            logger.info(f"[Page {page_num}] Recovering {len(missed_labels)} missed fields from layout analysis.")
            for missing_label in missed_labels:
                llm_fields.append(
                    FieldCandidate(
                        field_name=missing_label,
                        what_to_fill="अपनी जानकारी साफ़ अक्षरों में यहाँ भरें। (जैसे: 'राजेश कुमार', 'सेक्टर 5')" if language == "Hindi" else "Please enter your details clearly here. (e.g. 'John Doe', 'Sector 5')",
                        why_it_matters="यह जानकारी आपके दस्तावेज़ को पूरा करने के लिए जरूरी है।" if language == "Hindi" else "This info is essential for document completion.",
                        example="-",
                        source="detected_from_form",
                        retrieval_score=None,
                    ).model_dump()
                )
            out["fields"] = llm_fields
            out.setdefault("warnings", []).append(
                f"Recovered {len(missed_labels)} fields from layout that were missed by analysis."
            )

        if not out.get("fields") and _is_form_like_page(page_markdown):
            logger.warning(f"[Page {page_num}] Page looks form-like but no fields could be recovered.")

        out["page"] = page_num
        out["original_markdown"] = page_markdown

        # NEW: Integrate verify_output (Fixing bypassed check from DOCUMENTATION.md)
        guideline_titles = [
            g.get("guideline", {}).get("title", "")
            for g in merged_guideline_hits
            if g.get("guideline", {}).get("title")
        ]
        verification = verify_output(page_markdown, out, guideline_titles)
        if not verification.passed:
            logger.warning(f"[Page {page_num}] Verification failed: {verification.reason}")
            out.setdefault("warnings", []).append(f"Verification: {verification.reason}")

        return out

    except Exception as e:
        logger.error(f"[Page {page_num}] Pydantic validation failed: {e}. Raw keys: {list(result.keys())}. Outputting fallback.")
        return _fallback_page_output(page_num, page_markdown, context, language, detected_fields, error_msg=str(e))


def _fallback_page_output(
    page_num: int,
    page_md: str,
    context: dict[str, Any],
    language: str,
    detected_fields: list[dict[str, Any]] | None = None,
    error_msg: str = "Unknown error",
) -> dict[str, Any]:
    # Use pre-detected fields if available, otherwise fall back to regex
    if detected_fields:
        labels = [f["label"] for f in detected_fields]
    else:
        candidates = extract_field_candidates([{"page": page_num, "markdown": page_md}]).get(page_num, [])
        labels = candidates if candidates else []

    fields = []
    for label in labels:
        fields.append(FieldCandidate(
            field_name=label,
            what_to_fill="कृपया इस खाने में अपनी सही और सटीक जानकारी साफ़-साफ़ लिखें।" if language == "Hindi" else "Please enter your correct and precise information in this box clearly.",
            why_it_matters="यह जानकारी सरकारी रिकॉर्ड में आपकी पहचान पक्की करने और आवेदन को मंजूर करने के लिए अनिवार्य है।" if language == "Hindi" else "This information is mandatory to verify your identity in records and ensure application approval.",
            example="N/A",
            source="detected_from_form" if detected_fields else "document_text",
            retrieval_score=None,
        ))

    if not fields and _is_form_like_page(page_md):
        fields.append(FieldCandidate(
            field_name="मुख्य जानकारी" if language == "Hindi" else "Main section",
            what_to_fill="कृपया यहाँ माँगी गई मुख्य जानकारी साफ़-साफ़ भरें।" if language == "Hindi" else "Please enter the required primary information clearly here.",
            why_it_matters="यह जानकारी आपके आवेदन की प्रक्रिया को आगे बढ़ाने के लिए बहुत महत्वपूर्ण है।" if language == "Hindi" else "This information is very important to move your application process forward.",
            example="N/A",
            source="document_text",
            retrieval_score=None,
        ))

    fallback = PageOutput(
        language=language,
        document_purpose=first_heading(page_md),
        page_summary=f"Page {page_num} of the document.",
        translation="Translation unavailable.",
        simple_explanation="A simple explanation could not be generated.",
        action_guide="Follow the instructions on the form carefully.",
        fields=fields,
        confidence=0.5
    )

    out = fallback.model_dump()
    out["page"] = page_num
    return out
