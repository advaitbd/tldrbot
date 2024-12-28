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
        if user:
            prefix = f"_Conversation summarized by {user.name} for the last {message_count} messages:_\n\n"
        else:
            prefix = f"_Conversation summarized for the last {message_count} messages:_\n\n"
        return prefix + TextProcessor.escape_markdown(summary)
