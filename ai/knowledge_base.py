"""General cardiac-health reference content for SmartCare AI's retrieval step,
plus functions to seed it into Chroma and query it. This is general educational
information, not personalized medical advice — the agent is instructed to treat
it that way (see ai/smartcare_agent.py)."""
from ai.vectorstore import get_collection

DEFAULT_DOCS = [
    {
        "id": "kb-bp-1",
        "topic": "blood_pressure",
        "text": (
            "Blood pressure is recorded as two numbers, systolic over diastolic, measured in mmHg. "
            "A normal adult reading is roughly below 120/80. Readings consistently at or above 130/80 "
            "are generally considered elevated or hypertensive, and very low readings (below about "
            "90/60) may indicate hypotension. Only a doctor can interpret an individual reading in context."
        ),
    },
    {
        "id": "kb-hr-1",
        "topic": "heart_rate",
        "text": (
            "Resting heart rate for most healthy adults falls between 60 and 100 beats per minute. "
            "Well-conditioned athletes often have lower resting rates. A rate consistently above 100 bpm "
            "at rest (tachycardia) or below 60 bpm (bradycardia) without an obvious cause is worth "
            "discussing with a doctor."
        ),
    },
    {
        "id": "kb-troponin-1",
        "topic": "troponin",
        "text": (
            "Troponin is a protein released into the blood when heart muscle is damaged. Elevated "
            "troponin levels can indicate a heart attack or other cardiac injury. Reference ranges vary "
            "by lab, but any elevated troponin result should be evaluated promptly by a physician."
        ),
    },
    {
        "id": "kb-ef-1",
        "topic": "ejection_fraction",
        "text": (
            "Ejection fraction measures the percentage of blood pumped out of the heart's left ventricle "
            "with each contraction. A normal ejection fraction is generally 55% to 70%. Lower values can "
            "indicate heart failure or reduced pumping function and should be reviewed with a cardiologist."
        ),
    },
    {
        "id": "kb-lifestyle-1",
        "topic": "lifestyle",
        "text": (
            "Heart-healthy habits generally include regular moderate exercise, a diet rich in vegetables, "
            "fruits, whole grains and lean protein, limiting sodium and saturated fat, not smoking, "
            "moderating alcohol, managing stress, and getting consistent sleep. These habits support "
            "healthy blood pressure, cholesterol, and weight."
        ),
    },
    {
        "id": "kb-emergency-1",
        "topic": "emergency",
        "text": (
            "Seek emergency medical care immediately for chest pain or pressure, pain spreading to the "
            "arm or jaw, shortness of breath, sudden weakness or numbness, fainting, or a very fast or "
            "irregular heartbeat with dizziness. These can be signs of a heart attack or stroke and "
            "should never be evaluated by an AI assistant alone."
        ),
    },
    {
        "id": "kb-ecg-1",
        "topic": "ecg",
        "text": (
            "An ECG or EKG records the heart's electrical activity. Sinus rhythm is the normal pattern. "
            "Terms like sinus tachycardia (fast but regular rhythm starting in the normal pacemaker) or "
            "arrhythmia (irregular rhythm) describe deviations that a doctor interprets alongside the "
            "full clinical picture."
        ),
    },
    {
        "id": "kb-pulse-ox-1",
        "topic": "pulse_oximetry",
        "text": (
            "Pulse oximetry estimates the percentage of oxygen-saturated blood. Readings of 95% to 100% "
            "are typically considered normal for most people. Readings persistently below 92% may "
            "warrant medical attention, especially alongside symptoms like shortness of breath."
        ),
    },
]


def seed_knowledge_base():
    """Idempotent — safe to call every app startup. Only writes if the collection is empty."""
    collection = get_collection()
    existing_count = collection.count()
    if existing_count > 0:
        return {"seeded": 0, "already_present": existing_count}

    collection.add(
        ids=[d["id"] for d in DEFAULT_DOCS],
        documents=[d["text"] for d in DEFAULT_DOCS],
        metadatas=[{"topic": d["topic"]} for d in DEFAULT_DOCS],
    )
    return {"seeded": len(DEFAULT_DOCS), "already_present": 0}


def retrieve_context(query: str, k: int = 4):
    """Returns the k most relevant reference chunks for a query, or [] if the KB is empty."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(k, collection.count()))
    return results.get("documents", [[]])[0]