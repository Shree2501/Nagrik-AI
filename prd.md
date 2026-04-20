# Nagrik-AI: Comprehensive Project Report
**Empowering Rural Citizens Through AI-Driven Civic Document Literacy**

---

## 1. Introduction
Nagrik-AI is a voice-first civic document assistant designed to bridge the literacy gap for over 300 million citizens in rural India. While government services are rapidly digitizing, the language of administration remains filled with complex legal jargon and non-localized terminology. Nagrik transforms these documents from "walls of text" into actionable, spoken guides in local languages like Hindi.

### The Problem
*   **High Rejection Rates**: 30% of civic forms are rejected due to simple errors.
*   **Language Barrier**: Complex English/Hindi legal terms are often unintelligible to semi-literate users.
*   **Accessibility**: Most tools are desktop-first; rural users are mobile-first and voice-preferring.

---

## 2. System Workflow

### 2.1 External Workflow (User Journey)
1.  **Intake**: User takes a photo of a document or uploads a PDF.
2.  **Guided Analysis**: The app runs an asynchronous processing job.
3.  **Interactive Results**: User sees a simplified summary, page-by-page field guides, and crucial warnings.
4.  **Audio Assistance**: User listens to a high-fidelity audio summary generated in their native tongue.
5.  **Multi-turn QA**: User taps a microphone to ask specific questions like *"Where do I find my Ward number?"*

### 2.2 Internal Workflow (Technical Pipeline)
The system operates as a state-of-the-art AI pipeline:
1.  **FastAPI Job Orchestrator**: Receives the file and assigns a unique `job_id`.
2.  **Mistral OCR**: Extracts markdown and structural bounding boxes.
3.  **DocumentGraph Analysis**: Sections are linked across pages to provide "contextual depth."
4.  **Hybrid RAG (Retrieval-Augmented Generation)**: Searches local civic guidelines in **ChromaDB** using semantic embeddings.
5.  **Mistral LLM Core**: Generates localized explanations based on the "Comprehension Level" (Literal, Simple, or Rural).
6.  **Audio Synthesis**: Summary is passed to **ElevenLabs** or **gTTS** for final audio delivery.


## 3. System Architecture Diagrams

### 3.1 End-to-End Analysis Pipeline
![image](https://www.image2url.com/r2/default/images/1776515527325-f1344818-db89-4311-a333-699c7b8cf016.png)

### 3.2 Structural Memory (The "Missing Layer" in typical AI)
Unlike standard chatbots that treat text as a flat string, Nagrik builds a hierarchical graph to maintain context across physical page boundaries.
![image](https://www.image2url.com/r2/default/images/1776516074139-40c5ae2d-0462-4bd7-bb32-ea0c56676d3c.png)

### 3.3 Multi-Level Personalization Flow
![image](https://www.image2url.com/r2/default/images/1776516242787-4cf45dce-61e3-44dc-8c84-6a403a657568.png)

## 4. Case Study: Nagrik vs. Jugalbandi AI

**Jugalbandi AI** is a benchmark project by Microsoft and AI4Bharat using WhatsApp/Voice to help find government schemes. While transformative, our analysis identifies specific gaps that Nagrik-AI is designed to solve.

| Point of Comparison | Jugalbandi AI | Nagrik-AI |
| :--- | :--- | :--- |
| **Core Objective** | **Scheme Discovery**: "What am I eligible for?" | **Actionable Completion**: "How do I fill this paper?" |
| **Data Ingestion** | Primary focus on static PDFs of government rules. | High-fidelity OCR of user-uploaded physical forms. |
| **Structural Awareness** | Treats text as a flat conversational context. | **`DocumentGraph`** mapping to physical page/layout. |
| **Hallucination Risk** | General LLM responses can stray into generic advice. | **Surgical RAG** checks every field against verified rules. |
| **Accessibility Gap** | Text-heavy chat bubbles on WhatsApp. | **Voice-First Dashboard** with visual field highlighting. |

### Where Jugalbandi Lacks
1.  **Layout Blindness**: Jugalbandi cannot tell a user where a specific signature box is located on Page 3. It doesn't "see" the form.
2.  **Context Fragmentation**: In long forms, chat-based AI often forgets details from early pages.
3.  **Action Bias**: It informs the user, but doesn't guide their hand while they hold a pen.

### How Nagrik Improves the Journey
1.  **Visual Grounding**: Nagrik maps analysis directly to OCR blocks, allowing us to eventually overlay highlights on a digital copy of the form.
2.  **Cross-Page Memory**: Using `DocumentGraph`, Nagrik knows that the "Aadhaar" field on Page 1 is the same context as the "Identity Proof" requirement on Page 5.
3.  **Proactive Validation**: Nagrik transitions from discovery to *verification*—checking if the user's filled draft contains errors (Checklist feature).

---

## 5. Key Milestones

| Milestone | Phase | Key Deliverable | Status |
| :--- | :--- | :--- | :--- |
| **M1: MVP Launch** | **Alpha** | Mistral OCR integration & basic Hindi support | **Completed** |
| **M2: Structural Logic** | **Beta** | `DocumentGraph` for multi-page forms | **Completed** |
| **M3: Surgical RAG** | **Beta** | ChromaDB integration for high-accuracy grounding | **Completed** |
| **M4: NGO Pilot** | **V1.0** | Offline-capable caches & Community deployment | *Planned* |
| **M5: Govt API Sync** | **V2.0** | Direct data push to ServicePlus / Umang | *Future* |

---

## 6. Data Privacy & User Control
Nagrik-AI adopts a **"Transient State"** privacy model:
1.  **PII Sanitization**: Only the document content is sent to the LLM; user identities are not linked to document processing.
2.  **Stateless API**: Temporary files are deleted immediately after the JSON analysis is generated and summarized to audio.
3.  **On-Device History**: Analysis results are stored in the user's local `localStorage`, keeping history private on their device.
4.  **No Data Mining**: Collected guidelines are public civic data; user documents are never used for retraining.

---

## 7. Market Validation (Google Forms Survey)
To further refine the project, we propose the following survey for early testers (NGOs, Village Common Service Centers):

1.  **How accurately did the app identify the fields?** (Scale 1-5)
2.  **Which language do you struggle with the most on government forms?** (Checkboxes)
3.  **Would you prefer a real-time "Sign here" indicator over a summary?** (Yes/No)
4.  **What is the one form you find impossible to fill without help?** (Short Answer)
5.  **Rate the clarity of the voice summary.** (Scale 1-5)

---

## 8. Conclusion
Nagrik-AI is more than a translator; it is a "Digital Sahayak" (Helper). By combining **Structural Graph Logic** with **Surgical RAG**, it ensures that the complexities of bureaucracy do not stand in the way of a citizen's rights. The next phase will focus on community distribution and expanding to all 22 official languages of India.

