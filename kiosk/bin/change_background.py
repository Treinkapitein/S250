#!/usr/bin/python
"""
Draw the Support number to sys background images
2011-11-30 Sam: Created
2012-02-24 Justin: Image quality set to 100 when image format is JPEG.
"""
import shutil
import os
import datetime
import hashlib
try:
    from pysqlite2 import dbapi2 as sqlite
except:
    import sqlite3 as sqlite

from PIL import ImageFont, Image, ImageDraw

KIOSK_CONF = "/etc/kioskhome"
file = open(KIOSK_CONF, 'r')
KIOSK_HOME = file.readline().strip()

DB_PATH = os.path.join(KIOSK_HOME, "kiosk/var/db/mkc.db")
PATH = os.path.join(KIOSK_HOME, "kiosk/var/gui/sys/")
IMGS = ["bg_outofservice.png", "remote_reboot.jpg", "remotely_maintaining.jpg"]

def draw_text(text, image_path, file_name):
    try:
        max_l = 30
        a = text[:max_l].rfind(" ")
        if a > 0:
           text_l = [text[:a], text[a:]]
        else:
           text_l = [text[:35], text[35:]]
        font_file_path = os.path.dirname(__file__)
        # draw the text into the image
        im = Image.open(os.path.join(image_path, file_name))
        font_txt = ImageFont.truetype(os.path.join(font_file_path, "ARIAL.TTF"), 35)
        draw = ImageDraw.Draw(im)
        if text:
            draw.text((60, 940), "Please", font=font_txt, fill=(0, 0, 0))
            draw.text((180, 940), "contact:", font=font_txt, fill=(0, 0, 0))
            draw.text((320, 940), text_l[0], font=font_txt, fill=(0, 0, 0))
            draw.text((100, 975), text_l[1], font=font_txt, fill=(0, 0, 0))
        if im.format == 'JPEG':
            #Save image quality to 100 when background is JPEG format.
            im.save(os.path.join(image_path, file_name), im.format, quality=100)
        else:
            im.save(os.path.join(image_path, file_name), im.format)
    except:
        pass

def get_text():
    res = ""
    try:
        con = sqlite.connect(DB_PATH, timeout=10, isolation_level='IMMEDIATE')
        con.text_factory = str
        sql = "select value from config where variable ='tech_support_contact';"
        row = con.execute(sql).fetchone()
        if row:
            if row[0]:
                res = row[0]
    except Exception, ex:
        print str(ex)
    return res

def main():
    try:
        text = get_text()
        for img in IMGS:
            bak_file = img+".bak"
            y_file = os.path.join(PATH, bak_file)
            b_file = os.path.join(PATH, img)
            if (os.path.exists(os.path.join(PATH, bak_file)) == False):  
                shutil.copyfile(b_file, y_file)
            else:
                shutil.copyfile(y_file, b_file)
            draw_text(text, PATH, img)
    except Exception, ex:
        print str(ex)
    
if __name__ == "__main__":
    main()
