import unittest

from auris.speech_text import infer_speech_sentiment, normalise_spoken_text, prepare_speech


class SpeechTextTests(unittest.TestCase):
    def test_passive_listening_acknowledgements_are_silent(self):
        for text in ("YES DEVANSH I AM LISTENING", "Yes, Devansh. I am listening.", "Yes, Devansh, I am listening.", "I'm listening, Devansh."):
            with self.subTest(text=text):
                self.assertEqual(normalise_spoken_text(text), "")

    def test_acknowledgement_is_removed_without_losing_actual_result(self):
        self.assertEqual(normalise_spoken_text("**Yes, Devansh, I am listening.** Opened Notepad."), "Opened Notepad.")
        self.assertEqual(normalise_spoken_text("I am listening to the microphone recording to identify the error."), "I am listening to the microphone recording to identify the error.")

    def test_markdown_symbols_links_and_code_are_not_spoken_literally(self):
        text = normalise_spoken_text(
            "## **Warning**\n* The result is *verified*.\n"
            "Read [the report](https://example.com/report) and calculate 2 * 3.\n"
            "```python\nprint('*')\n```"
        )

        self.assertNotIn("*", text)
        self.assertNotIn("https", text)
        self.assertNotIn("```", text)
        self.assertIn("Warning", text)
        self.assertIn("the report", text)
        self.assertIn("2 times 3", text)

    def test_decorative_symbols_and_citations_are_removed(self):
        text = normalise_spoken_text("Ready \u2605 [12]. AURIS uses the API/UI path.")

        self.assertNotIn("\u2605", text)
        self.assertNotIn("[12]", text)
        self.assertIn("Auris", text)
        self.assertIn("A P I", text)
        self.assertIn("U I", text)

    def test_standalone_asterisks_and_decorative_dashes_are_silent(self):
        text = normalise_spoken_text("*Important* --- the task is **ready**.")

        self.assertEqual(text, "Important. the task is ready.")

    def test_concern_takes_priority_over_positive_words(self):
        sentiment, confidence, signals = infer_speech_sentiment(
            "The deployment failed, although the database remains healthy."
        )

        self.assertEqual(sentiment, "concerned")
        self.assertGreaterEqual(confidence, 0.7)
        self.assertIn("failure reported", signals)

    def test_plan_adapts_pace_and_energy_without_claiming_emotion(self):
        concerned = prepare_speech("I would recommend against sending it. There is a material risk.")
        positive = prepare_speech("The task is completed and verified.")

        self.assertEqual(concerned.sentiment, "concerned")
        self.assertEqual(concerned.energy, "measured")
        self.assertLess(concerned.speed, positive.speed)
        self.assertLessEqual(concerned.confidence, 1.0)

    def test_output_is_bounded_at_a_sentence_or_word(self):
        text = normalise_spoken_text(("This is a complete sentence. " * 100) + "tail")

        self.assertLessEqual(len(text), 1201)
        self.assertTrue(text.endswith("."))


if __name__ == "__main__":
    unittest.main()
