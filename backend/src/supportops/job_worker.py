"""Run the single local mock analysis worker."""
import argparse
import time

from sqlalchemy.orm import Session

from supportops.config import load_settings
from supportops.db import make_engine
from supportops.generation import MockGeneration, OllamaGeneration
from supportops.jobs import claim_job, execute_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--model", help="Local Ollama generation model")
    parser.add_argument("--digest", help="Full SHA-256 digest of the local model")
    args = parser.parse_args()
    if bool(args.model) != bool(args.digest):
        parser.error("--model and --digest must be supplied together")
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    if settings.analysis_loop == "langgraph":
        from supportops.agent_graph import ensure_no_external_tracing

        ensure_no_external_tracing()
    engine = make_engine(settings.database_url)
    provider = OllamaGeneration(args.model, settings.embedding_url, digest=args.digest) if args.model else MockGeneration()
    try:
        while True:
            with Session(engine) as session, session.begin():
                claimed = claim_job(session)
            if claimed:
                execute_job(engine, *claimed, provider, loop=settings.analysis_loop)
            if args.once:
                break
            if not claimed:
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
