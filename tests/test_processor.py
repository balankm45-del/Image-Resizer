import sys
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processor import process_image


class ProcessorTests(unittest.TestCase):
    def test_process_image_resizes_a_real_png(self):
        image = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        result = process_image(
            input_bytes=image_bytes,
            filename="sample.png",
            resize_mode="dimensions",
            width="100",
            height="100",
            percentage="100",
            keep_aspect=True,
            format_ext="png",
            quality="80",
        )

        output_bytes, download_filename, out_w, out_h, out_size = result
        self.assertTrue(output_bytes)
        self.assertTrue(download_filename.endswith(".png"))
        self.assertGreater(out_w, 0)
        self.assertGreater(out_h, 0)
        self.assertGreater(out_size, 0)


if __name__ == "__main__":
    unittest.main()
