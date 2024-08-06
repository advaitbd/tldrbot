def filter_bot_messages(result):
    return [message for message in result if not message.startswith("tldrbot:")]

def count_words(result):
    return sum(len(message.split()) for message in result)

def censor_result(result, words_to_censor):
    redacted_result = []
    for message in result:
        words = message.split()
        redacted_words = []
        for word in words:
            if word.lower() in words_to_censor:
                redacted_words.append("[REDACTED]")
            elif any(word.lower() in censor_word for censor_word in words_to_censor if len(word.lower()) >= 4):
                redacted_words.append("[REDACTED]")
            elif any(censor_word.lower() in word.lower() for censor_word in words_to_censor):
                redacted_words.append("[REDACTED]")
            else:
                redacted_words.append(word)
        redacted_result.append(" ".join(redacted_words))
    return redacted_result
