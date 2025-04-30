# Dissemination-plan
Technical Overview for Data Scientists
This project implements an automated Erasmus+ Dissemination Plan generator built entirely in Python using the Streamlit framework. It enables the user to upload a .pdf or .docx project proposal and dynamically generates a full, 12-section Dissemination & Communication Plan based on the semantic content of the proposal.

The tool is not based on LLM generation, but rather on a lightweight, efficient pipeline combining:

 1. Document Parsing
Uses PyMuPDF (fitz) for extracting text from .pdf files and python-docx for .docx proposals.

Full text is processed and cleaned before further analysis.

 2. Semantic Embedding & Retrieval
Text is chunked into 500-character segments.

Each chunk is embedded using MiniLM-L6-v2 from sentence-transformers (a distilled transformer model optimized for speed and semantic similarity).

A FAISS Index (L2) is constructed on the embeddings.

For each semantic category (objectives, target groups, etc.), query embeddings are matched against the index to extract the top-k relevant chunks.

This technique allows the system to semantically locate relevant project content even if the proposal has inconsistent formatting or lacks formal section headings.

 3. Keyword Extraction & Cleaning
Simple regex-based matching is used to extract:

Project Title or Project Acronym

Objectives, Results, Challenges, Target Groups

A clean_keywords() function removes trivial, noisy, or low-information phrases (e.g., "working with", "to improve") and provides default fallbacks.

Additional checks ensure the extracted project_name is not a placeholder like "progress project".

 4. Structured Generation (No LLM)
Each dissemination section (1–12) is generated using hard-coded, multi-paragraph scaffolds that are dynamically populated using:

the extracted keywords,

the project name,

the sector (field) context (e.g., renewable energy, VET, etc.).

No external API calls are made. The result is a fully explainable, deterministic, and reproducible output—ideal for public project deliverables.

 5. UI & State Management
Built with Streamlit, the UI supports:

File uploads (pdf, docx)

Real-time section generation

Sidebar navigation and plan preview

Export to .md (future: .docx)

All persistent state (project name, context, selected section, etc.) is handled using st.session_state.

 Dependencies
streamlit

faiss-cpu

sentence-transformers

PyMuPDF (fitz)

python-docx

re, numpy, datetime

 Design Philosophy
This tool is designed to be:

Fast: avoids the overhead of full LLMs

Transparent: outputs are predictable and verifiable

Customizable: prompts and templates can be adapted to different project types

LLM-optional: the codebase is compatible with future integration of OpenAI, Hugging Face, or private model inference for more flexible generation

 Summary
This project demonstrates how a structured NLP pipeline using lightweight transformer-based models and rule-based logic can automate complex document generation tasks—such as writing detailed Dissemination Plans for EU-funded projects—without relying on commercial LLMs.

It is ideal for data scientists working in:

education / research tech,

NLP for document automation,

proposal writing tools,

knowledge extraction from unstructured text.
