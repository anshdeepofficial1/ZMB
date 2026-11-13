import sys
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import graphic_novel as a
from visual_manifest import day1_episode
from animate import Shot, Texts
from svgrender import font_map

class GraphicNovelTest(unittest.TestCase):
    def test_each_authored_beat_has_distinct_moving_valid_svg(self):
        ep=day1_episode()
        shots=[Shot("line",i*4,4,text=v["text"],meta=v["shot"]) for i,v in enumerate(ep["lines"])]
        txt=Texts(font_map(Path(__file__).resolve().parents[1]))
        cache={}
        views=[]
        for i,shot in enumerate(shots):
            first=a.frame_svg(ep,{},shots,i*4+.18,txt,cache)
            later=a.frame_svg(ep,{},shots,i*4+3.5,txt,cache)
            ET.fromstring(first)
            ET.fromstring(later)
            self.assertNotEqual(first,later)
            self.assertNotEqual(a.scene(shot.meta["beat"],.18,.04),a.scene(shot.meta["beat"],3.5,.88))
            views.append(first)
        self.assertEqual(len(set(views)),7)
    def test_physical_ignition_flashlight_and_knob(self):
        self.assertNotEqual(a.cabin(.1,.1),a.cabin(2,.8))
        self.assertIn("#ffeab2",a.scene("flashlight_exit",3,.9))
        self.assertNotIn("#ffeab2",a.scene("flashlight_exit",.1,.03))
        self.assertIn("rotate(65)",a.close_door(4,1,True))
        self.assertNotIn("LAST LIGHT  /  OPEN 24H",a.scene("car_driving",1,.25))
        self.assertIn("LAST LIGHT  /  OPEN 24H",a.scene("spot_station",1,.25))
