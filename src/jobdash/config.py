"""Settings you are expected to edit."""

# Approximate conversion rates to EUR. They only need to be close enough to
# compare roles; update them if you want today's numbers.
FX_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.86,
    "GBP": 1.15,
    "INR": 0.0098,
    "SGD": 0.66,
    "AUD": 0.56,
    "HKD": 0.11,
    "JPY": 0.0058,
    "SEK": 0.090,
    "DKK": 0.134,
    "NOK": 0.085,
    "CHF": 1.07,
    "CAD": 0.62,
    "PLN": 0.235,
}

# Your skills, compared against each role's tech stack to compute skill_match_pct.
# Use the normalised spelling (the right-hand side of STACK_ALIASES).
MY_SKILLS = [
    "Python", "TypeScript", "JavaScript", "Go", "React", "Next.js", "Node.js",
    "FastAPI", "PostgreSQL", "Redis", "Docker", "AWS", "LLM APIs", "RAG",
    "LangGraph", "LangChain", "SSE", "WebSockets", "REST APIs", "Celery",
    "SQLAlchemy", "Supabase", "Qdrant", "Agentic AI",
]

# Different spellings of the same technology -> one canonical tag (keys lowercase).
STACK_ALIASES = {
    "go (golang)": "Go", "golang": "Go",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "react.js": "React", "reactjs": "React", "react": "React",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "next.js": "Next.js", "nextjs": "Next.js",
    "typescript": "TypeScript", "ts": "TypeScript",
    "javascript": "JavaScript", "js": "JavaScript",
    "python": "Python", "async python": "Python",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "aws": "AWS", "gcp": "GCP", "docker": "Docker", "redis": "Redis",
    "llms": "LLM APIs", "llm apis": "LLM APIs", "llm integration": "LLM APIs",
    "rag pipelines": "RAG", "rag": "RAG",
    "agentic ai": "Agentic AI", "ai agents": "Agentic AI",
    "rest apis": "REST APIs", "rest api": "REST APIs",
    "websockets": "WebSockets", "graphql": "GraphQL",
}
