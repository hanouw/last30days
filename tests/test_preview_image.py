import unittest

from weekly_brief import PreviewImageParser, preview_image


class PreviewImageTests(unittest.TestCase):
    def test_reads_article_social_image(self):
        parser = PreviewImageParser()
        parser.feed('<meta property="og:image" content="https://example.com/story.jpg">')
        self.assertEqual(parser.image, "https://example.com/story.jpg")

    def test_skips_non_https_article(self):
        self.assertEqual(preview_image("http://example.com/story"), "")


if __name__ == "__main__":
    unittest.main()
