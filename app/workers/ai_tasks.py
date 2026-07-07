from app.queues.celery_app import celery_app
from app.services.candidate_scorer_service import CandidateScorerService
from app.services.interview_service import InterviewService
from app.services.resume_analyzer_service import ResumeAnalyzerService


@celery_app.task(name="ai.resume_analyze", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def analyze_resume_task(self, payload: dict) -> dict:
    return ResumeAnalyzerService().analyze(payload)


@celery_app.task(name="ai.candidates_score_batch", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def score_candidates_task(self, payload: dict) -> dict:
    return CandidateScorerService().score_batch(payload)


@celery_app.task(name="ai.interview_generate", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_interview_task(self, payload: dict) -> dict:
    return InterviewService().generate(payload)
