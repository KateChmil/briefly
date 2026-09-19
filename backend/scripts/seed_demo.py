"""Fill the database with realistic demo data — no Anthropic API key needed.

Handy as a safety net for the live demo (Wi-Fi or API trouble) and for developing
the UI without spending tokens.

    cd backend
    python -m scripts.seed_demo          # add demo subjects
    python -m scripts.seed_demo --reset  # wipe everything first
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Artifact,
    ArtifactKind,
    CalendarEvent,
    ChatMessage,
    Source,
    SourceOrigin,
    SpaceStatus,
    StudySession,
    SubjectSpace,
)

TODAY = date.today()


def day(n: int) -> date:
    return TODAY + timedelta(days=n)


def read_mock(team: str, channel: str, name: str) -> str:
    return (Path(settings.mock_teams_dir) / team / channel / name).read_text(encoding="utf-8")


BIO_NOTES = """# Biology 101 — Key notes

## Cells
- **Prokaryotes** have no nucleus; **eukaryotes** have membrane-bound organelles.
- **Mitochondria** produce ATP through cellular respiration.
- The **ribosome** builds proteins from mRNA.

## Genetics
- DNA is a double helix of nucleotides (A–T, G–C).
- **Mendel's laws:** segregation and independent assortment.
- A Punnett square predicts offspring genotype ratios.

## Must remember
1. Respiration: glucose + O₂ → CO₂ + H₂O + ATP
2. Transcription (DNA → mRNA) happens in the nucleus; translation (mRNA → protein) at the ribosome.
"""

BIO_QUIZ = {
    "title": "Biology 101 — practice test",
    "questions": [
        {"type": "mcq", "question": "Which organelle produces most of the cell's ATP?",
         "choices": ["Nucleus", "Mitochondria", "Golgi apparatus", "Ribosome"],
         "answer": "Mitochondria", "explanation": "Mitochondria are the site of cellular respiration."},
        {"type": "mcq", "question": "In a Bb × Bb cross, what fraction of offspring are homozygous recessive?",
         "choices": ["0", "1/4", "1/2", "3/4"], "answer": "1/4",
         "explanation": "A Punnett square gives BB, Bb, Bb, bb — one in four is bb."},
        {"type": "mcq", "question": "Where does translation take place?",
         "choices": ["Nucleus", "Ribosome", "Mitochondrion", "Cell membrane"], "answer": "Ribosome",
         "explanation": "Ribosomes read mRNA and assemble the protein."},
        {"type": "short", "question": "What does DNA stand for?", "answer": "Deoxyribonucleic acid",
         "explanation": "The molecule that carries genetic information."},
    ],
}

BIO_CARDS = {
    "cards": [
        {"front": "Powerhouse of the cell?", "back": "The mitochondrion — it makes ATP."},
        {"front": "Prokaryote vs eukaryote", "back": "Prokaryotes lack a nucleus and membrane-bound organelles."},
        {"front": "Mendel's law of segregation", "back": "Each parent passes on one of its two alleles for a trait."},
        {"front": "Transcription", "back": "DNA is copied into mRNA in the nucleus."},
        {"front": "Translation", "back": "Ribosomes build a protein from the mRNA sequence."},
        {"front": "Genotype vs phenotype", "back": "Genotype is the alleles you carry; phenotype is the trait you show."},
    ]
}


def plan(overview: str, sessions: list[tuple[int, str, str, int, str]]) -> tuple[str, list[dict]]:
    rows = [
        {"date": day(d).isoformat(), "title": t, "topic": topic, "minutes": m, "kind": k}
        for d, t, topic, m, k in sessions
    ]
    return json.dumps({"overview": overview, "sessions": rows}, indent=2), rows


def add_space(db, name, exam_in, profile, sessions, overview, notes, quiz, cards, sources, done):
    space = SubjectSpace(
        name=name,
        status=SpaceStatus.ready,
        profile={**profile, "exam_date": day(exam_in).isoformat()},
    )
    db.add(space)
    db.flush()

    for team, channel, fname in sources:
        db.add(Source(
            space_id=space.id, origin=SourceOrigin.teams, filename=fname, mime_type="",
            storage_path="", extracted_text=read_mock(team, channel, fname),
            teams_ref={"file_id": f"{team}/{channel}/{fname}"},
        ))

    content, rows = plan(overview, sessions)
    for kind, fmt, body in (
        (ArtifactKind.study_plan, "json", content),
        (ArtifactKind.notes, "markdown", notes),
        (ArtifactKind.sample_test, "json", json.dumps(quiz, indent=2)),
        (ArtifactKind.flashcards, "json", json.dumps(cards, indent=2)),
    ):
        db.add(Artifact(space_id=space.id, kind=kind, format=fmt, content=body, version=1))
    for i, r in enumerate(rows):
        db.add(StudySession(space_id=space.id, date=date.fromisoformat(r["date"]), title=r["title"],
                            topic=r["topic"], minutes=r["minutes"], kind=r["kind"], done=i < done))

    db.add_all([
        ChatMessage(space_id=space.id, role="assistant",
                    content=f"Hi! I'm Briefly, your study assistant for **{name}**. When is your exam?"),
        ChatMessage(space_id=space.id, role="user",
                    content=f"My exam is in {exam_in} days and I can study about {profile['weekly_hours']} hours a week."),
        ChatMessage(space_id=space.id, role="assistant",
                    content="Thanks! I've built your study plan, notes, a sample test and flashcards. "
                            "Ask me anything, or tell me if your schedule changes."),
    ])
    return space


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if "--reset" in sys.argv:
        for model in (ChatMessage, Source, Artifact, StudySession, CalendarEvent, SubjectSpace):
            db.query(model).delete()
        db.commit()

    bio_overview = (
        "Start with cell structure, then genetics, and finish with two full practice "
        "rounds.\n\n- **Weeks 1–2:** concepts and notes\n- **Week 3:** practice questions and flashcards\n"
        "- **Final days:** mock exam and light review"
    )
    bio = add_space(
        db, "Biology 101", 12,
        {"goal": "Pass the final exam", "level": "intermediate", "weekly_hours": 6,
         "weak_topics": ["genetics"]},
        [(-2, "Cell structure", "cell-biology.txt", 45, "study"),
         (-1, "Organelles review", "cell-biology.txt", 30, "review"),
         (0, "Genetics: Mendel", "genetics-overview.txt", 60, "study"),
         (1, "Punnett square practice", "genetics-overview.txt", 45, "practice"),
         (3, "Cell respiration", "lab-guidelines.txt", 45, "study"),
         (5, "Flashcards sprint", "All topics", 30, "review"),
         (7, "Genetics problem set", "genetics-overview.txt", 60, "practice"),
         (9, "Mock exam", "All topics", 90, "mock_exam"),
         (11, "Final review", "Weak topics", 45, "review")],
        bio_overview, BIO_NOTES, BIO_QUIZ, BIO_CARDS,
        [("Biology 101", "Lectures", "cell-biology.txt"), ("Biology 101", "Lectures", "genetics-overview.txt")],
        # Nothing done: the two sessions in the past are overdue, so the demo
        # can show the one-click "Reschedule" catch-up planner.
        done=0,
    )

    calc = add_space(
        db, "Calculus II", 20,
        {"goal": "Score 80%+ on the midterm", "level": "beginner", "weekly_hours": 5,
         "weak_topics": ["series", "integration by parts"]},
        [(0, "Integration by parts", "integration-techniques.txt", 60, "study"),
         (2, "Substitution drills", "week5-practice.txt", 45, "practice"),
         (6, "Sequences and series", "series-and-sequences.txt", 60, "study"),
         (10, "Convergence tests", "series-and-sequences.txt", 45, "study"),
         (14, "Problem set review", "week5-practice.txt", 60, "review"),
         (18, "Mock midterm", "All topics", 90, "mock_exam")],
        "Daily short drills beat weekend cramming. Do the problem set twice.",
        "# Calculus II — notes\n\n## Integration by parts\n∫u dv = uv − ∫v du\n\n## Series\nA series converges if the partial sums approach a limit.",
        {"title": "Calculus II — practice test", "questions": [
            {"type": "short", "question": "State the integration by parts formula.", "answer": "∫u dv = uv − ∫v du", "explanation": "Choose u to simplify when differentiated."},
            {"type": "mcq", "question": "Does the harmonic series converge?", "choices": ["Yes", "No"], "answer": "No", "explanation": "It diverges, slowly."},
            {"type": "short", "question": "Derivative of ln(x)?", "answer": "1/x", "explanation": "Basic derivative."}]},
        {"cards": [{"front": "Ratio test", "back": "Converges if lim |a(n+1)/a(n)| < 1."},
                   {"front": "∫ 1/x dx", "back": "ln|x| + C"},
                   {"front": "Geometric series sum", "back": "a / (1 − r) when |r| < 1"},
                   {"front": "p-series converges when", "back": "p > 1"}]},
        [("Calculus II", "Lectures", "integration-techniques.txt")],
        done=0,
    )

    for offset, start, end, title, kind, space in [
        (1, "09:00", "10:30", "Biology 101 lecture", "class", bio),
        (3, "14:00", "15:30", "Calculus II lecture", "class", calc),
        (4, "10:00", "12:00", "Biology lab session", "class", bio),
        (8, "09:00", "10:30", "Biology 101 lecture", "class", bio),
        (10, "14:00", "15:30", "Calculus II lecture", "class", calc),
        (13, None, None, "Calculus II homework due", "other", calc),
    ]:
        db.add(CalendarEvent(space_id=space.id, title=title, date=day(offset), start_time=start,
                             end_time=end, kind=kind, source="manual"))
    db.commit()
    db.close()
    print("Seeded Biology 101 and Calculus II (exams in 12 and 20 days).")


if __name__ == "__main__":
    main()
