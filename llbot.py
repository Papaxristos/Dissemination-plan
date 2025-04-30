# Refactored llbot.py (Streamlined and Modular)

import streamlit as st
import fitz  # PyMuPDF
import docx
import numpy as np
import faiss
import re
import requests
from sentence_transformers import SentenceTransformer
from io import BytesIO
from docx import Document
from datetime import datetime

st.set_page_config(page_title="Erasmus+ Dissemination Plan Creator", page_icon="🤖", layout="wide")

# === Session Initialization ===
def init_session_state():
    defaults = {
        "messages": [], "section_titles": [], "selected_title": None,
        "context": "", "section_text": None, "project_title": "Unnamed_Project",
        "generated_sections": {}, "export_ready": False
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

# === File Handling ===
def upload_proposal_file():
    uploaded_file = st.file_uploader("\U0001F4E4 Upload your Erasmus+ Proposal (PDF or DOCX)", type=["pdf", "docx"])
    if uploaded_file and not st.session_state.section_titles:
        text_output = extract_text_from_file(uploaded_file)
        st.session_state.project_title = extract_project_name(text_output)
        st.success(f"📌 Project title: {st.session_state.project_title.replace('_', ' ')}")
        st.session_state.context = extract_clean_context(text_output)
        return True
    return False

def extract_text_from_file(uploaded_file):
    text_output = ""
    if uploaded_file.name.lower().endswith(".pdf"):
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            for page in doc:
                text_output += page.get_text()
    elif uploaded_file.name.lower().endswith(".docx"):
        docx_file = docx.Document(uploaded_file)
        for para in docx_file.paragraphs:
            text_output += para.text + "\n"
    return text_output

def extract_project_title(text_output):
    """Final safe export of project title avoiding wrong matches."""
    
    blacklist_words = [
    "summary", "applicant", "application", "organisation", "partner", "work package",
    "budget", "call", "deadline", "action type", "priority", "activities",
    "table of contents", "contents", "introduction", "background",
    "background and experience", "relevance of the project"
    ]



    lines = text_output.splitlines()

    for line in lines:
        clean_line = line.strip()
        if len(clean_line) > 10:
            if any(bad_word in clean_line.lower() for bad_word in blacklist_words):
                continue  # Ignore bad words
            if re.match(r'^[A-Z][A-Za-z0-9\s\-]{5,100}$', clean_line):
                return clean_line.replace(" ", "_")[:50]
    
    # === Fallback ===
    return st.session_state.project_title

# === Context Extraction ===
def extract_clean_context(text_output):
    chunks = [text_output[i:i+500] for i in range(0, len(text_output), 500)]
    model_emb = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model_emb.encode(chunks)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings))
    query_terms = ["project objectives", "target groups", "stakeholders", "impact", "dissemination", "communication strategy", "project results", "sustainability"]

    relevant_chunks = []
    for query in query_terms:
        query_embedding = model_emb.encode([query])
        D, I = index.search(np.array(query_embedding), k=3)
        relevant_chunks.extend([chunks[idx] for idx in I[0]])

    clean_context = "\n".join([
        line.strip() for chunk in relevant_chunks for line in chunk.splitlines()
        if len(line.strip()) > 30 and len(line.strip().split()) > 5
    ])
    return clean_context

# === Sidebar ===
def render_sidebar():
    with st.sidebar:
        st.header("\U0001F4CB Navigation")
        st.info("1. Upload proposal\n2. Review context\n3. Generate sections\n4. Export final plan")
        if st.session_state.section_titles:
            st.subheader("Quick Navigation")
            for title in st.session_state.section_titles:
                if st.button(f"Go to {title.split('.')[0]}", key=f"nav_{title}"):
                    st.session_state.selected_title = title
                    st.experimental_rerun()
        if st.session_state.generated_sections:
            if st.button("\U0001F4E5 Export Complete Plan"):
                st.session_state.export_ready = True
                st.experimental_rerun()

# === Section Buttons and Content ===
def render_section_buttons():
    if st.session_state.section_titles and not st.session_state.export_ready:
        st.subheader("\U0001F9E9 Click a section title to generate content:")
        cols = st.columns(2)
        for i, title in enumerate(st.session_state.section_titles):
            col = cols[i % 2]
            if col.button(f"{title}"):
                st.session_state.selected_title = title
                st.session_state.section_text = None

def render_selected_section():
    if st.session_state.selected_title and not st.session_state.export_ready:
        selected = st.session_state.selected_title
        st.subheader(f"\U0001F4DD {selected}")
        if not st.session_state.section_text:
            with st.spinner(f"✍️ Generating {selected}..."):
                st.session_state.section_text = generate_section_content(selected, st.session_state.context)
        st.markdown(st.session_state.section_text)
        st.session_state.generated_sections[selected] = st.session_state.section_text


def extract_keywords(context):
    """Improved extraction of key keywords from project context."""

    keywords = {}

    # === 1. Project Name Extraction ===
    project_name_match = re.search(r'project\s+(?:title|name)?\s*:?\s*[“"«]?\s*([A-Z][A-Za-z0-9\s\-]{3,80})[”"»]?', context, re.IGNORECASE)
    if project_name_match:
        keywords["project_name"] = project_name_match.group(1).strip()
    else:
        keywords["project_name"] = st.session_state.project_title.replace("_", " ")

    # === 2. Objectives Extraction ===
    objectives = re.findall(r'(?:objective|aim|goal)[s]*[:\s]*(.{10,150})[.;]', context, re.IGNORECASE)
    objectives_clean = [obj.strip().capitalize() for obj in objectives if len(obj.strip().split()) > 3]
    if objectives_clean:
        keywords["project_objectives"] = objectives_clean[:2]
    else:
        keywords["project_objectives"] = ["improve education quality", "promote innovation"]

    # === 3. Results Extraction ===
    results = re.findall(r'(?:result|output|deliverable)[s]*[:\s]*(.{10,150})[.;]', context, re.IGNORECASE)
    results_clean = [res.strip().capitalize() for res in results if len(res.strip().split()) > 3]
    if results_clean:
        keywords["project_results"] = results_clean[:2]
    else:
        keywords["project_results"] = ["curriculum development", "training materials"]

    # === 4. Challenges Extraction ===
    challenges = re.findall(r'(?:challenge|problem|issue)[s]*[:\s]*(.{10,150})[.;]', context, re.IGNORECASE)
    challenges_clean = [cha.strip().capitalize() for cha in challenges if len(cha.strip().split()) > 3]
    if challenges_clean:
        keywords["project_challenges"] = challenges_clean[:2]
    else:
        keywords["project_challenges"] = ["skills gaps", "low VET attractiveness"]

    # === 5. Field Extraction ===
    if "renewable energy" in context.lower():
        keywords["field"] = "renewable energy"
    elif "digital skills" in context.lower() or "digital education" in context.lower():
        keywords["field"] = "digital education"
    elif "social inclusion" in context.lower():
        keywords["field"] = "social inclusion"
    else:
        keywords["field"] = "education"

    # === 6. Target Groups Extraction ===
    target_groups = []
    if "students" in context.lower():
        target_groups.append("students")
    if "teachers" in context.lower() or "educators" in context.lower():
        target_groups.append("teachers")
    if "policy makers" in context.lower():
        target_groups.append("policy makers")
    if "youth workers" in context.lower():
        target_groups.append("youth workers")

    if target_groups:
        keywords["target_groups"] = target_groups[:3]
    else:
        keywords["target_groups"] = ["students", "educators", "stakeholders"]

        # === POST-PROCESSING for keywords ===

    def clean_keywords(keywords):
        """It cleans up keywords (objectives, results, challenges, project name) so that they can be used in the text."""

    def clean_keyword(kw):
        """Cleans up single or misspelled keywords."""
        kw = kw.strip()
        if len(kw.split()) < 3 or any(bad in kw.lower() for bad in [" and ", " with ", " to ", "ing", " from "]):
            return None
        return kw

    # Cleaning project objectives
    if "project_objectives" in keywords:
        cleaned_objectives = [clean_keyword(obj) for obj in keywords["project_objectives"]]
        keywords["project_objectives"] = [obj for obj in cleaned_objectives if obj] or [
            "Improve education quality", "Promote innovation"
        ]

    # Cleaning project results
    if "project_results" in keywords:
        cleaned_results = [clean_keyword(res) for res in keywords["project_results"]]
        keywords["project_results"] = [res for res in cleaned_results if res] or [
            "Curriculum development", "Training materials"
        ]

    # Cleaning project challenges
    if "project_challenges" in keywords:
        cleaned_challenges = [clean_keyword(cha) for cha in keywords["project_challenges"]]
        keywords["project_challenges"] = [cha for cha in cleaned_challenges if cha] or [
            "Skills gaps", "Low VET attractiveness"
        ]

    # Check project name
    if "project_name" in keywords:
        if len(keywords["project_name"].split()) < 2 or "progress" in keywords["project_name"].lower():
            keywords["project_name"] = st.session_state.project_title.replace("_", " ").strip().title()

    return keywords


def is_valid_title(title: str) -> bool:
    """Checks if the title is real."""
    blacklist = [
        "table of contents", "applicant", "summary", 
        "application form", "background", "relevance"
    ]
    title_lower = title.lower()
    return (
        len(title.split()) >= 2 and
        not any(bad_word in title_lower for bad_word in blacklist) and
        not re.match(r'^[A-Z\s]+$', title)  # Not entirely capitalized
    )

def clean_title(title: str) -> str:
    """Cleans up the title by removing special symbols."""
    return re.sub(r'[^\w\s-]', '', title).strip()


def extract_project_name(full_text: str) -> str:
    """Extracts a title or acronym from the ENTIRE sentence text."""
    # 1. Project Title (various variations)
    title_patterns = [
        r'Project Title\s*:?\s*[\n\s]*([^\n]+)',
        r'Title of (?:the )?Project\s*:?\s*[\n\s]*([^\n]+)',
        r'^#\s*(.+)$',  # Markdown-style title
    ]
    for pattern in title_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            if is_valid_title(title):
                return clean_title(title)

    # 2. Project Acronym
    acronym_match = re.search(r'Project Acronym\s*:?\s*[\n\s]*([A-Z0-9]{2,20})', full_text, re.IGNORECASE)
    if acronym_match:
        return clean_title(acronym_match.group(1).strip())

    # 3. Fallback: single capital title
    standalone_title = re.search(r'^\s*([A-Z][A-Z0-9\s\-]{5,50})\s*$', full_text, re.MULTILINE)
    if standalone_title and is_valid_title(standalone_title.group(1)):
        return clean_title(standalone_title.group(1))

    return "Unnamed_Project"


# === Generate Section Content ===
def generate_section_content(section_title, context):
    """Creates a personalized text for the Dissemination Plan in report format."""
    keywords = extract_keywords(context)
    project_name = st.session_state.project_title.replace("_", " ").strip()
    field = keywords.get("field", "education").lower()
    objectives = keywords.get("project_objectives", ["improve quality", "promote innovation"])
    results = keywords.get("project_results", ["curriculum development", "training materials"])
    challenges = keywords.get("project_challenges", ["skills gaps"])
    target_groups = keywords.get("target_groups", ["students", "teachers", "stakeholders"])
    challenge_text = challenges[0] if challenges else "key challenges"

    if "1. Introduction" in section_title:
        return f"""
The {project_name} project, developed under the Erasmus+ framework, seeks to address systemic challenges in the {field} sector, primarily focusing on {challenge_text.lower()}. It aims to provide forward-looking solutions that equip learners and professionals with the necessary tools to succeed in an evolving socio-economic landscape. The project directly engages {", ".join(target_groups)} by introducing innovative, evidence-based approaches that promote active learning and green transition.

One of the central goals of the initiative is to {objectives[0].lower()}, while also seeking to {objectives[1].lower()} at both institutional and policy levels. To reach these goals, the consortium will develop key outputs such as {results[0]} and {results[1]}, which are expected to strengthen both formal and non-formal education pathways.

The project is anchored in the European Green Deal and supports the broader objectives of resilience, inclusion, and sustainability. Through its comprehensive dissemination strategy, it will ensure that the outcomes have a lasting impact across regions, sectors, and target populations.

Furthermore, the project's vision aligns with global sustainability agendas, promoting skills that respond to the demands of the green economy. It also serves as a model of cross-sector collaboration, where stakeholders from education, industry, and government come together to co-create impactful solutions.
"""

    elif "2. Dissemination Objectives" in section_title:
        return f"""
The dissemination strategy of the {project_name} project is structured to maximize the visibility and impact of its activities and outputs. The key dissemination objectives are to raise awareness among {", ".join(target_groups)}, promote the adoption of innovative methodologies such as {results[0]}, and encourage sustainable integration of project results into existing educational and professional practices within the {field} field.

The dissemination objectives also include building trust among stakeholders, ensuring that communication is inclusive, transparent, and responsive to feedback. By tailoring messages to specific audiences and leveraging both traditional and digital media, the project fosters meaningful engagement.

By strategically engaging with stakeholders throughout the project's lifecycle, the consortium aims to ensure that the project's value extends far beyond its completion. This involves continuous knowledge sharing, open access to resources, and fostering ambassadors among participants to carry forward the project's legacy.
"""

    elif "3. Target Groups" in section_title:
        return f"""
The {project_name} project targets a wide range of audiences to ensure broad dissemination and effective impact. Primary target groups include {target_groups[0]} and {target_groups[1]}, who are essential for implementing and benefiting from the project's innovations.

Additionally, policy makers and institutional leaders are engaged to support the institutionalization and scalability of project outcomes, thus ensuring systemic change within the {field} sector. Specific actions will be adapted to the needs and realities of each group, ensuring inclusivity and relevance.

The project also identifies secondary audiences such as parents, career advisors, and media professionals, who act as multipliers in promoting project results. These groups are reached through targeted campaigns and community-based events, ensuring holistic dissemination coverage.
"""

    elif "4. Project Identity" in section_title:
        return f"""
A strong and coherent project identity is critical for the success of dissemination efforts. The {project_name} project has developed a comprehensive visual identity that reflects its mission, values, and focus on innovation within the {field} sector. This identity serves as a unifying element across all activities, ensuring consistency in both internal communication and external visibility.

Standardized templates for reports, presentations, newsletters, and social media posts have been developed. These materials integrate the official Erasmus+ branding guidelines and project-specific visual elements (e.g., logo, typography, color palette), promoting a professional and recognizable image at all touchpoints.

A detailed branding manual has been distributed to all partners, outlining clear instructions on the correct and consistent use of visual elements. All partners are expected to apply this identity in their local dissemination efforts to maintain uniformity and increase the credibility and recognizability of the project at national and European levels.

The visual identity will also be regularly evaluated and adapted if necessary to maintain relevance and accessibility for all stakeholders.
"""

    elif "5. Dissemination Channels" in section_title:
        return f"""
To reach the intended audiences effectively, the {project_name} project utilizes a variety of dissemination channels. A dedicated website serves as the central hub for all public information, while social media platforms such as LinkedIn, Twitter, and Facebook are employed to amplify project news and updates.

Workshops, conferences, and targeted events are organized to engage stakeholders directly, promoting dialogue and knowledge exchange within the {field} community. Print materials such as leaflets and posters complement digital efforts, particularly in community-based outreach.

In addition, the project leverages newsletters, podcasts, and short videos to engage audiences across age groups and learning preferences. These are shared via mailing lists and hosted on a user-friendly content platform.
"""

    elif "6. Internal Communication" in section_title:
        return f"""
Efficient internal communication among project partners is vital to ensure coherent dissemination. The {project_name} consortium employs digital collaboration tools such as Slack and Microsoft Teams to maintain continuous communication and coordination.

Regular virtual meetings and annual in-person consortium gatherings are scheduled to review dissemination progress and align strategies across all participating organizations. Each partner has a designated communication liaison to streamline messaging and document sharing.

Moreover, a shared knowledge base and internal calendar keep partners aligned on milestones, deadlines, and dissemination deliverables.
"""

    elif "7. Communication Guidelines" in section_title:
        return f"""
All communication efforts within the {project_name} project adhere to clearly established guidelines to ensure consistency, professionalism, and alignment with Erasmus+ values.

These guidelines define the tone, terminology, approval procedures, and branding requirements for all public-facing materials, ensuring the project's voice is unified and impactful across all platforms.

The communication protocol also includes crisis communication scenarios, ensuring the consortium can respond rapidly to misinformation, misinterpretation, or reputational risk.
"""

    elif "8. Dissemination Activities" in section_title:
        return f"""
Each partner in the {project_name} project is actively involved in dissemination activities tailored to local and national contexts. Activities include organizing awareness-raising workshops, publishing articles in professional journals, and establishing direct relationships with key stakeholders such as policy makers and industry leaders.

These activities are planned and monitored through a shared dissemination calendar, and partners are encouraged to include their networks in multiplying the reach. All dissemination efforts are documented using a standard reporting template to ensure transparency and collective evaluation.

Peer-learning events between partners are also foreseen to exchange good practices and refine dissemination methods in real time.
"""

    elif "9. Timeline" in section_title:
        return f"""
The dissemination timeline of the {project_name} project is carefully structured to align with key project milestones. Initial activities focus on building awareness and establishing the project's presence online and in professional communities.

As the project progresses, dissemination intensifies with regular events, publications, and stakeholder engagements. Final dissemination efforts are concentrated on ensuring the long-term uptake and sustainability of project results.

A visual Gantt chart accompanies the timeline, outlining communication milestones, lead responsibilities, and deadlines, providing a clear roadmap for partners.
"""

    elif "10. Monitoring" in section_title:
        return f"""
Monitoring the effectiveness of dissemination activities is a continuous priority for the {project_name} project. Key metrics include website analytics, social media engagement rates, and attendance figures at dissemination events.

Regular feedback is collected from participants and stakeholders, and quarterly internal reviews are conducted to evaluate performance and adapt strategies as necessary.

A centralized monitoring dashboard is maintained by the dissemination lead, providing real-time insights and allowing data-driven decision-making.
"""

    elif "11. Key Performance" in section_title:
        return f"""
To measure the success of dissemination efforts, the {project_name} project has established a set of Key Performance Indicators (KPIs). These include achieving over 5,000 website visits, engaging more than 1,000 participants in events, building a social media following of 2,000+, and securing at least 20 media mentions across partner countries.

KPIs are reviewed at regular intervals in consortium meetings and used to shape the communication strategy dynamically. Feedback loops are established to ensure that underperforming channels are re-evaluated and adjusted.
"""

    elif "12. Sustainability" in section_title:
        return f"""
The {project_name} project is committed to ensuring the long-term sustainability of its results beyond the funding period. Strategies include maintaining the project website as a knowledge hub, embedding project outputs into partner institutions' curricula, and fostering alumni networks to sustain professional collaboration.

The consortium also aims to transfer project results to other sectors through collaboration with umbrella organizations, networks, and policymakers, multiplying the project’s impact across fields.

Dissemination tools and materials will remain open-access, and partners are encouraged to continue their use and promotion after the project’s formal closure.
"""
    
    else:
        return f"""
This section ({section_title}) will be dynamically generated based on the extracted project keywords and specific context details.
"""


# === Export Plan ===
def export_complete_plan():
    if st.session_state.export_ready:
        complete_text = """# Dissemination and Communication Plan\n\n"""
        complete_text += f"## {st.session_state.project_title.replace('_', ' ')}\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        for title, content in st.session_state.generated_sections.items():
            complete_text += f"## {title}\n\n{content}\n\n"
        st.download_button("Download Plan (Markdown)", complete_text, f"{st.session_state.project_title}_Plan.md", "text/markdown")

# === Footer ===
def render_footer():
    st.markdown("---")
    st.markdown("Tool developed to generate Erasmus+ dissemination plans.")

# === Main App ===
def main():
    st.title("\U0001F916 Erasmus+ Dissemination Plan Creator")
    init_session_state()
    render_sidebar()
    if upload_proposal_file():
        st.subheader("\U0001F50D Project Context")
        st.markdown(st.session_state.context or "_No valid context extracted._")
        st.session_state.section_titles = [
            "1. Introduction and Overview",
            "2. Dissemination Objectives and Strategy",
            "3. Target Groups and Stakeholders",
            "4. Project Identity and Branding",
            "5. Dissemination Channels and Tools",
            "6. Internal Communication Strategy",
            "7. Communication Guidelines for Partners",
            "8. Dissemination Activities by Partner",
            "9. Timeline and Milestones",
            "10. Monitoring and Evaluation of Dissemination Activities",
            "11. Key Performance Indicators (KPIs)",
            "12. Sustainability and Long-term Impact"
        ]
    render_section_buttons()
    render_selected_section()
    export_complete_plan()
    render_footer()

if __name__ == "__main__":
    main()