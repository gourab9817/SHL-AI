from app.chat_history import build_assistant_history_content


def test_build_assistant_history_content_appends_recommendation_names() -> None:
    content = "Here are the best matches."
    recommendations = [
        {"name": "Core Java (Advanced Level) (New)", "test_type": "K", "url": "https://example.com/java"},
        {"name": "Docker (New)", "test_type": "K", "url": "https://example.com/docker"},
    ]

    serialized = build_assistant_history_content(content, recommendations)

    assert "Here are the best matches." in serialized
    assert "Catalog recommendations shared:" in serialized
    assert "- Core Java (Advanced Level) (New) [K]" in serialized
    assert "- Docker (New) [K]" in serialized


def test_build_assistant_history_content_returns_plain_content_without_recommendations() -> None:
    assert build_assistant_history_content("Only a reply.", []) == "Only a reply."
