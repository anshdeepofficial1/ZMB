"""Contract tests for ComfyUI adapter. No server, model, or API credits needed."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import comfyui_cinematic as cc
from visual_manifest import VisualContractError


class BindingsTests(unittest.TestCase):
    def test_strict_api_node_editing_and_not_ui_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp, "workflow.json")
            flow.write_text(json.dumps({
                "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "OLD"}},
                "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "unused"}},
                "10": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
            }))
            spec = {
                "workflow_file": "workflow.json",
                "prompt": ["6", "text"],
                "reference_nodes": {"max": ["10", "image"]},
                "output_node": "9",
            }
            with patch.object(cc, "ROOT", Path(tmp)):
                prepared = cc.prepare_workflow(
                    spec, prompt="The car drives down the highway",
                    references={"max": "approved_max.png"},
                )
                self.assertIn("The car drives", prepared["6"]["inputs"]["text"])
                self.assertEqual(prepared["10"]["inputs"]["image"], "approved_max.png")
                self.assertEqual(
                    json.loads(flow.read_text())["6"]["inputs"]["text"], "OLD",
                    "Original API workflow must not mutate",
                )

    def test_unbound_character_reference_refuses_to_generate(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "flow.json").write_text(json.dumps({
                "6": {"inputs": {"text": ""}},
            }))
            with patch.object(cc, "ROOT", Path(tmp)):
                with self.assertRaisesRegex(VisualContractError, "lacks reference"):
                    cc.prepare_workflow(
                        {"workflow_file": "flow.json", "prompt": ["6", "text"]},
                        prompt="A person moves",
                        references={"biscuit": "dog.png"},
                    )

    def test_invalid_node_rejected(self):
        with self.assertRaisesRegex(VisualContractError, "missing node/input"):
            cc.set_input({"6": {"inputs": {"text": ""}}}, ["7", "text"], "new")

    def test_select_output_uses_expected_node_and_extension(self):
        record = {"outputs": {"9": {"images": [
            {"filename": "still.png", "subfolder": "", "type": "output"},
        ]}, "58": {"gifs": [
            {"filename": "video.mp4", "subfolder": "video", "type": "output"},
        ]}}}
        self.assertEqual(cc.select_output(record, "9", ".png")["filename"], "still.png")
        self.assertEqual(cc.select_output(record, "58", ".mp4")["filename"], "video.mp4")
        with self.assertRaisesRegex(VisualContractError, "no output"):
            cc.select_output(record, "9", ".mp4")

    def test_bindings_must_have_video_source_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "config.json")
            p.write_text(json.dumps({
                "image": {"workflow_file": "x.json", "prompt": ["1", "text"], "output_node": "9"},
                "video": {"workflow_file": "y.json", "prompt": ["2", "text"], "output_node": "58"},
            }))
            with self.assertRaisesRegex(VisualContractError, "actual approved/generated image"):
                cc.load_bindings(p)


class ComfyAPITests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, body, *, raw=b""):
            self.body, self.raw = body, raw
        def raise_for_status(self):
            return None
        def json(self):
            return self.body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def iter_content(self, chunk_size):
            yield self.raw

    def test_real_api_queue_and_history_protocol(self):
        client = cc.ComfyClient("http://127.0.0.1:8188")
        count = []
        def route(method, url, **kwargs):
            count.append((method, url))
            if url.endswith("/prompt"):
                self.assertEqual(kwargs["json"]["prompt"]["6"]["inputs"]["text"], "render")
                return self.FakeResponse({"prompt_id": "job123"})
            if url.endswith("/history/job123"):
                return self.FakeResponse({"job123": {
                    "status": {"completed": True, "status_str": "success"},
                    "outputs": {"9": {"images": [{"filename": "scene.png", "type": "output"}]}}
                }})
            raise AssertionError(url)
        client.http.request = route
        result = client.execute({"6": {"inputs": {"text": "render"}}})
        self.assertIn("9", result["outputs"])
        self.assertEqual(len(count), 2)

    def test_reject_invalid_video_without_persisting_file(self):
        client = cc.ComfyClient("http://127.0.0.1:8188")
        client.http.get = lambda *args, **kwargs: self.FakeResponse(
            {}, raw=b"not a real MP4" * 100
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "clip.mp4")
            with self.assertRaisesRegex(VisualContractError, "invalid MP4"):
                client.download({"filename": "clip.mp4"}, p)
            self.assertFalse(p.exists())
            self.assertFalse(Path(str(p) + ".partial").exists())

    def test_same_sedan_reference_required_for_exterior_and_interior(self):
        from visual_manifest import build_manifest, day1_episode
        shots = build_manifest(day1_episode())["shots"]
        ids = lambda shot: {p["id"] for p in shot["prop_references"]}
        self.assertIn("sedan", ids(shots[0]))
        self.assertIn("sedan", ids(shots[1]))
        self.assertIn("sedan", ids(shots[2]))
        self.assertIn("station", ids(shots[5]))
        self.assertIn("station", ids(shots[6]))
        self.assertIn("RECURRING PROP sedan:", shots[0]["prompt"])

    def test_preflight_refuses_missing_real_car_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("image_api.json", "video_api.json"):
                (root / name).write_text(json.dumps({
                    "6": {"inputs": {"text": ""}},
                    "12": {"inputs": {"image": "sample.png"}},
                    "58": {"inputs": {"filename_prefix": "video"}},
                }))
            spec = {
                "image": {
                    "workflow_file": "image_api.json",
                    "prompt": ["6", "text"], "output_node": "58",
                },
                "video": {
                    "workflow_file": "video_api.json",
                    "prompt": ["6", "text"], "source_image": ["12", "image"],
                    "output_node": "58",
                },
            }
            assets = [{"characters": [], "prop_references": [{"id": "sedan"}]}]
            with patch.object(cc, "ROOT", root):
                with self.assertRaisesRegex(VisualContractError, "approved reference for sedan"):
                    cc.validate_generation_preflight(
                        assets, spec, {}, {"sedan": {"reference": "missing_hero_sedan.png"}}
                    )

    def test_generated_provenance_is_unreviewed(self):
        import inspect
        source = inspect.getsource(cc.generate_shot)
        self.assertIn('"UNREVIEWED"', source)
        self.assertIn('"publishing_authorized": False', source)


if __name__ == "__main__":
    unittest.main()
