class TextProcessor:
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape markdown special characters."""
        special_chars = ['[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        escaped_text = text
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f"\\{char}")
        return escaped_text

    @staticmethod
    def format_summary_message(summary: str, user: object, message_count: int) -> str:
        """Format the summary message with user info and message count."""
        user_name = getattr(user, "name", None) if user is not None else None
        if user_name is not None:
            prefix = f"_Conversation summarized by {user_name} for the last {message_count} messages:_\n\n"
        else:
            prefix = f"_Conversation summarized for the last {message_count} messages:_\n\n"
        return prefix + TextProcessor.escape_markdown(summary)
