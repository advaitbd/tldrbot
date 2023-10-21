from summarizer import Summarizer


def get_summary(result):
    model = Summarizer()
    summary = model(result, min_length=60)
    full = "".join(summary)
    return full
