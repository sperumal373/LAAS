"""Extract Wipro logo image bytes from template and save for reuse."""
from pptx import Presentation
from pptx.util import Inches
import io, os

prs = Presentation(r'C:\Users\Administrator\Desktop\Wipro Template.pptx')

# Logo is in Layout 0 as 'Graphic 10' - PICTURE shape
layout0 = prs.slide_layouts[0]
for shape in layout0.shapes:
    if shape.name == 'Graphic 10' and shape.shape_type == 13:
        img_blob = shape.image.blob
        ext = shape.image.ext
        outpath = rf'C:\caas-dashboard\wipro_logo.{ext}'
        with open(outpath, 'wb') as f:
            f.write(img_blob)
        print(f"Saved logo: {outpath} ({len(img_blob):,} bytes) ext={ext}")
        print(f"Logo position: left={shape.left} top={shape.top} w={shape.width} h={shape.height}")
        print(f"In inches: left={shape.left/914400:.3f} top={shape.top/914400:.3f} w={shape.width/914400:.3f} h={shape.height/914400:.3f}")
