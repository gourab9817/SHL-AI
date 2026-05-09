import warnings
import sys

# Suppress LangGraph and LangChain deprecation warnings before any imports
warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", module=".*langgraph.*")
warnings.filterwarnings("ignore", module=".*langchain.*")
