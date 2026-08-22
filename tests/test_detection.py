from pipeline.detection import VEHICLE_CLASS_MAP


def test_vehicle_class_map_covers_coco_vehicle_classes():
    assert VEHICLE_CLASS_MAP == {2: "car", 3: "bike", 5: "bus", 7: "truck"}


def test_vehicle_class_map_values_are_fr1_labels():
    assert set(VEHICLE_CLASS_MAP.values()) == {"car", "bike", "bus", "truck"}
