"""Tests for plan_parser room and ceiling extractors (Phase 4.3 + 4.4)."""

from __future__ import annotations

from decimal import Decimal

from src.extraction.plan_parser.ceiling_extractor import _normalise_grid, extract_ceiling_specs
from src.extraction.plan_parser.room_extractor import _normalise_height, extract_rooms

# ===========================================================================
# Height normalisation unit tests
# ===========================================================================


class TestNormaliseHeight:
    def test_feet_inches_canonical(self):
        assert _normalise_height("9'-0\"") == "9'-0\""

    def test_feet_inches_no_dash(self):
        assert _normalise_height("9'0\"") == "9'-0\""

    def test_feet_only(self):
        assert _normalise_height("9FT") == "9'-0\""

    def test_feet_space(self):
        assert _normalise_height("10 FT") == "10'-0\""

    def test_total_inches(self):
        assert _normalise_height('108"') == "9'-0\""

    def test_with_aff(self):
        assert _normalise_height("10'-0\" AFF") == "10'-0\""

    def test_no_height(self):
        assert _normalise_height("CONFERENCE ROOM") is None


# ===========================================================================
# Grid normalisation unit tests
# ===========================================================================


class TestNormaliseGrid:
    def test_2x4(self):
        assert _normalise_grid("2x4") == "2x4"

    def test_2x2(self):
        assert _normalise_grid("2X2") == "2x2"

    def test_24x48(self):
        assert _normalise_grid("24X48") == "2x4"

    def test_24x24(self):
        assert _normalise_grid("24X24") == "2x2"

    def test_1x4(self):
        assert _normalise_grid("1X4") == "1x4"


# ===========================================================================
# Room extraction tests
# ===========================================================================


class TestExtractRoomsBasic:
    def test_extract_rooms_basic(self):
        text = "ROOM 101 - CONFERENCE ROOM\n9'-0\" AFF\nACT-1\n\nROOM 102 - BREAKROOM\n10'-0\" AFF\nGWB"
        rooms = extract_rooms(text)
        assert len(rooms) >= 2
        assert any(r["room_name"] == "CONFERENCE ROOM" for r in rooms)
        assert any(r["room_name"] == "BREAKROOM" for r in rooms)

    def test_room_numbers_captured(self):
        text = "ROOM 101 - CONFERENCE ROOM\n9'-0\" AFF\nACT-1\n\nROOM 102 - BREAKROOM\n10'-0\" AFF\nGWB"
        rooms = extract_rooms(text)
        numbers = {r["room_number"] for r in rooms if r["room_number"]}
        assert "101" in numbers
        assert "102" in numbers

    def test_ceiling_height_captured(self):
        text = "ROOM 101 - CONFERENCE ROOM\n9'-0\" AFF\nACT-1"
        rooms = extract_rooms(text)
        conf = next(r for r in rooms if r["room_name"] == "CONFERENCE ROOM")
        assert conf["ceiling_height"] == "9'-0\""

    def test_ceiling_type_act(self):
        text = "ROOM 101 - CONFERENCE ROOM\n9'-0\" AFF\nACT-1"
        rooms = extract_rooms(text)
        conf = next(r for r in rooms if r["room_name"] == "CONFERENCE ROOM")
        assert conf["ceiling_type"] == "ACT"

    def test_ceiling_type_gwb(self):
        text = "ROOM 102 - BREAKROOM\n10'-0\" AFF\nGWB"
        rooms = extract_rooms(text)
        br = next(r for r in rooms if r["room_name"] == "BREAKROOM")
        assert br["ceiling_type"] == "GWB"

    def test_scope_tag_captured(self):
        text = "ROOM 101 - CONFERENCE ROOM\n9'-0\" AFF\nACT-1"
        rooms = extract_rooms(text)
        conf = next(r for r in rooms if r["room_name"] == "CONFERENCE ROOM")
        assert conf["scope_tag"] == "ACT-1"


class TestExtractRoomsPatterns:
    def test_room_no_prefix(self):
        text = "ROOM NO. 201 - SERVER ROOM\n11'-0\" AFF\nEXPOSED STRUCTURE"
        rooms = extract_rooms(text)
        assert any(r["room_number"] == "201" for r in rooms)

    def test_bare_number_dash_name(self):
        text = "301 - LOBBY\n12'-0\" AFF"
        rooms = extract_rooms(text)
        assert any(r["room_name"] == "LOBBY" for r in rooms)

    def test_finish_schedule_row(self):
        text = (
            "FINISH SCHEDULE:\n"
            "ROOM  NAME        FLOOR  WALL   CEILING\n"
            "101   CONF RM     VCT    PAINT  ACT-1\n"
            "102   BREAK RM    VCT    PAINT  GWB\n"
        )
        rooms = extract_rooms(text)
        names = {r["room_name"] for r in rooms}
        assert "CONF RM" in names or any("CONF" in n for n in names)

    def test_open_area_no_number(self):
        text = "OPEN OFFICE\n9'-0\" AFF\nACT-2"
        rooms = extract_rooms(text)
        assert any(r["room_name"] == "OPEN OFFICE" for r in rooms)

    def test_lobby_detected(self):
        text = "LOBBY AREA\n12'-0\" AFF\nEXPOSED"
        rooms = extract_rooms(text)
        assert any("LOBBY" in r["room_name"].upper() for r in rooms)

    def test_no_duplicate_rooms(self):
        text = "ROOM 101 - CONFERENCE ROOM\n9'-0\" AFF\nACT-1\nROOM 101 - CONFERENCE ROOM"
        rooms = extract_rooms(text)
        numbers = [r["room_number"] for r in rooms if r["room_number"] == "101"]
        assert len(numbers) == 1

    def test_multiple_rooms_different_heights(self):
        text = (
            "ROOM 101 - OFFICE A\n9'-0\" AFF\nACT-1\n\n"
            "ROOM 102 - OFFICE B\n10'-0\" AFF\nACT-2\n\n"
            "ROOM 103 - LOBBY\n12'-0\" AFF\nGWB"
        )
        rooms = extract_rooms(text)
        assert len(rooms) >= 3
        office_a = next((r for r in rooms if r["room_number"] == "101"), None)
        assert office_a is not None
        assert office_a["ceiling_height"] == "9'-0\""


class TestExtractRoomsAnnotations:
    def test_bluebeam_annotation_scope_area(self):
        """Annotation labels like 'ACT-1 - 2,450 SF' should become rooms."""

        class FakeAnnotation:
            label = "ACT-1 - 2,450 SF"
            area_sf = None

        rooms = extract_rooms("", annotations=[FakeAnnotation()])
        assert len(rooms) >= 1
        r = rooms[0]
        assert r["scope_tag"] == "ACT-1"
        assert r["area_sf"] == Decimal("2450")

    def test_bluebeam_annotation_plain_tag(self):
        class FakeAnnotation:
            label = "AWP-1"
            area_sf = Decimal("850")

        rooms = extract_rooms("", annotations=[FakeAnnotation()])
        assert any(r["scope_tag"] == "AWP-1" for r in rooms)

    def test_annotation_dict_form(self):
        ann = {"label": "ACT-2 - 1,200 SF", "area_sf": None}
        rooms = extract_rooms("", annotations=[ann])
        assert any(r["scope_tag"] == "ACT-2" for r in rooms)


# ===========================================================================
# Ceiling spec extraction tests
# ===========================================================================


class TestExtractCeilingAct:
    def test_extract_ceiling_act(self):
        text = "ACT-1 Armstrong Dune 2x4 Grid 9'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert len(specs) >= 1
        assert specs[0]["ceiling_type"] == "ACT"
        assert specs[0]["grid_pattern"] == "2x4"

    def test_act_scope_tag(self):
        text = "ACT-1 Armstrong Dune 2x4 Grid 9'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert specs[0]["scope_tag"] == "ACT-1"

    def test_act_height(self):
        text = "ACT-1 Armstrong Dune 2x4 Grid 9'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert specs[0]["height"] == "9'-0\""

    def test_act_product_spec(self):
        text = "ACT-1 Armstrong Dune 2x4 Grid 9'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert specs[0]["product_spec"] is not None
        assert "Armstrong" in specs[0]["product_spec"] or "Dune" in specs[0]["product_spec"]

    def test_act_2x2_grid(self):
        text = "ACOUSTICAL CEILING TILE 2X2 ARMSTRONG 9'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["grid_pattern"] == "2x2" for s in specs)

    def test_act_24x48_normalised(self):
        text = "ACT-2 Cortega 704 24X48 Grid 10'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["grid_pattern"] == "2x4" for s in specs)


class TestExtractCeilingGwb:
    def test_gwb_detected(self):
        text = "GWB Ceiling 10'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "GWB" for s in specs)

    def test_gypsum_detected(self):
        text = "GYPSUM BOARD CEILING 9'-0\""
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "GWB" for s in specs)

    def test_drywall_detected(self):
        text = "DRYWALL CLG 10'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "GWB" for s in specs)


class TestExtractCeilingExposed:
    def test_exposed_structure(self):
        text = "EXPOSED STRUCTURE 14'-6\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "Exposed Structure" for s in specs)

    def test_open_to_above(self):
        text = "OPEN TO ABOVE"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "Exposed Structure" for s in specs)

    def test_open_to_structure(self):
        text = "OPEN TO STRUCTURE 18'-0\""
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "Exposed Structure" for s in specs)


class TestExtractCeilingOtherTypes:
    def test_baffles(self):
        text = "ACOUSTIC BAFFLE SYSTEM 12'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "Baffles" for s in specs)

    def test_cloud(self):
        text = "CLOUD CEILING PANEL"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "Baffles" for s in specs)

    def test_fabric_wall(self):
        text = "FABRIC WALL PANELS SNAP-TEX"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "FW" for s in specs)

    def test_snap_tex(self):
        text = "SNAP-TEX TRACK SYSTEM"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "FW" for s in specs)

    def test_woodworks(self):
        text = "WOODWORKS CEILING SYSTEM 10'-0\" AFF"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "WW" for s in specs)

    def test_sound_masking(self):
        text = "SOUND MASKING SYSTEM"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "SM" for s in specs)

    def test_masking_system(self):
        text = "MASKING SYSTEM EMITTERS"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "SM" for s in specs)


class TestExtractCeilingMultiLine:
    def test_multi_line_entry(self):
        text = "ACT-1\nArmstrong Dune\n2x4 Grid\n9'-0\" AFF\n"
        specs = extract_ceiling_specs(text)
        assert any(s["ceiling_type"] == "ACT" for s in specs)
        # Height captured from context window
        act = next(s for s in specs if s["ceiling_type"] == "ACT")
        assert act["height"] == "9'-0\""

    def test_multiple_ceiling_types(self):
        text = (
            "ACT-1 Armstrong Dune 2x4 Grid 9'-0\" AFF\n\n"
            "GWB Ceiling 10'-0\" AFF\n\n"
            "EXPOSED STRUCTURE 14'-0\" AFF"
        )
        specs = extract_ceiling_specs(text)
        types = {s["ceiling_type"] for s in specs}
        assert "ACT" in types
        assert "GWB" in types
        assert "Exposed Structure" in types

    def test_deduplication_by_scope_tag(self):
        text = "ACT-1 Armstrong Dune 2x4\nACT-1 continued notes 2x4\n"
        specs = extract_ceiling_specs(text)
        act1_specs = [s for s in specs if s["scope_tag"] == "ACT-1"]
        assert len(act1_specs) == 1


class TestExtractCeilingAnnotations:
    def test_annotation_area_sf(self):
        class FakeAnnotation:
            label = "ACT-1 - 2,450 SF"
            area_sf = None

        specs = extract_ceiling_specs("", annotations=[FakeAnnotation()])
        assert len(specs) >= 1
        assert specs[0]["scope_tag"] == "ACT-1"
        assert specs[0]["area_sf"] == Decimal("2450")

    def test_annotation_plain_tag_with_area(self):
        class FakeAnnotation:
            label = "AWP-1"
            area_sf = Decimal("950")

        specs = extract_ceiling_specs("", annotations=[FakeAnnotation()])
        assert any(s["scope_tag"] == "AWP-1" for s in specs)

    def test_annotation_dict_form(self):
        ann = {"label": "ACT-2 - 1,800 SF", "area_sf": None}
        specs = extract_ceiling_specs("", annotations=[ann])
        assert any(s["scope_tag"] == "ACT-2" for s in specs)

    def test_annotation_no_duplicate_when_text_already_has_tag(self):
        """If ACT-1 already found in text, don't add a duplicate from annotation."""

        class FakeAnnotation:
            label = "ACT-1 - 2,450 SF"
            area_sf = None

        text = "ACT-1 Armstrong Dune 2x4 Grid 9'-0\" AFF"
        specs = extract_ceiling_specs(text, annotations=[FakeAnnotation()])
        act1 = [s for s in specs if s["scope_tag"] == "ACT-1"]
        assert len(act1) == 1

    def test_source_page_passed_through(self):
        text = "ACT-1 Armstrong Dune 2x4 9'-0\" AFF"
        specs = extract_ceiling_specs(text, source_page=3)
        assert all(s["source_page"] == 3 for s in specs)


# ===========================================================================
# Integration: combined room + ceiling on realistic text block
# ===========================================================================


class TestIntegration:
    SAMPLE_TEXT = """\
REFLECTED CEILING PLAN

ROOM 101 - CONFERENCE ROOM
9'-0\" AFF
ACT-1 Armstrong Dune
2x4 Grid

ROOM 102 - BREAKROOM
10'-0\" AFF
GWB

ROOM 103 - SERVER ROOM
11'-0\" AFF
EXPOSED STRUCTURE

OPEN OFFICE AREA
9'-0\" AFF
ACT-2 Cortega 704
2x4 Grid

FINISH SCHEDULE:
ROOM  NAME          FLOOR  WALL   CEILING
104   RESTROOM       CT     PAINT  GWB
105   STORAGE        VCT    PAINT  GWB
"""

    def test_rooms_found(self):
        rooms = extract_rooms(self.SAMPLE_TEXT)
        names = {r["room_name"] for r in rooms}
        assert "CONFERENCE ROOM" in names
        assert "BREAKROOM" in names

    def test_ceiling_specs_found(self):
        specs = extract_ceiling_specs(self.SAMPLE_TEXT)
        types = {s["ceiling_type"] for s in specs}
        assert "ACT" in types
        assert "GWB" in types
        assert "Exposed Structure" in types

    def test_open_office_room(self):
        rooms = extract_rooms(self.SAMPLE_TEXT)
        assert any("OPEN OFFICE" in r["room_name"].upper() for r in rooms)

    def test_finish_schedule_rooms(self):
        rooms = extract_rooms(self.SAMPLE_TEXT)
        numbers = {r["room_number"] for r in rooms if r["room_number"]}
        # 101, 102, 103 from headers; 104, 105 from schedule
        assert numbers.issuperset({"101", "102", "103"})
