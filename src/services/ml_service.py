from typing import Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class MLService:
    def __init__(self):
        self._analyzer = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> Tuple[str, float]:
        if not text or not text.strip():
            return "neutral", 0.0

        scores = self._analyzer.polarity_scores(text)
        compound = scores["compound"]

        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return label, compound


ml_service = MLService()