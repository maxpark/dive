"""
VIAME Fish format deserializer
"""
import csv
import json
import re
import io
from dataclasses import dataclass, field
from dacite import from_dict, Config
from typing import List, Dict, Tuple, Optional, Union, Any

from girder.models.file import File


@dataclass
class Feature:
    """Feature represents a single detection in a track."""

    frame: int
    bounds: List[float]
    head: Optional[Tuple[float, float]] = None
    tail: Optional[Tuple[float, float]] = None
    fishLength: Optional[float] = None
    attributes: Optional[Dict[str, Union[bool, float, str]]] = None

    def asdict(self):
        """Removes entries with values of `None`."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Track:
    begin: int
    end: int
    trackId: int
    features: List[Feature] = field(default_factory=lambda: [])
    confidencePairs: List[Tuple[str, float]] = field(default_factory=lambda: [])
    attributes: Dict[str, Any] = field(default_factory=lambda: {})

    def asdict(self):
        """Used instead of `dataclasses.asdict` for better performance."""

        track_dict = dict(self.__dict__)
        track_dict["features"] = [
            feature.asdict() for feature in track_dict["features"]
        ]
        return track_dict


def row_info(row: List[str]) -> Tuple[int, int, List[float], float]:
    trackId = int(row[0])
    frame = int(row[2])

    bounds = [float(x) for x in row[3:7]]
    fish_length = float(row[8])

    return trackId, frame, bounds, fish_length


def _deduceType(value: str) -> Union[bool, float, str]:
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        number = float(value)
        return number
    except ValueError:
        return value


def _parse_row(row: List[str]) -> Tuple[Dict, Dict, Dict, List]:
    """
    parse a single CSV line into its composite track and detection parts
    """
    features = {}
    attributes = {}
    track_attributes = {}
    confidence_pairs = [
        [row[i], float(row[i + 1])]
        for i in range(9, len(row), 2)
        if not row[i].startswith("(")
    ]
    start = len(row) - 1 if len(row) % 2 == 0 else len(row) - 2

    for j in range(start, len(row)):
        if row[j].startswith("(kp)"):
            if "head" in row[j]:
                groups = re.match(r"\(kp\) head ([0-9]+) ([0-9]+)", row[j])
                if groups:
                    features["head"] = (groups[1], groups[2])
            elif "tail" in row[j]:
                groups = re.match(r"\(kp\) tail ([0-9]+) ([0-9]+)", row[j])
                if groups:
                    features["tail"] = (groups[1], groups[2])
        if row[j].startswith("(atr)"):
            groups = re.match(r"\(atr\) (.+) (.+)", row[j])
            if groups:
                attributes[groups[1]] = _deduceType(groups[2])
        if row[j].startswith("(trk-atr)"):
            groups = re.match(r"\(trk-atr\) (.+) (.+)", row[j])
            if groups:
                track_attributes[groups[1]] = _deduceType(groups[2])

    return features, attributes, track_attributes, confidence_pairs


def _parse_row_for_tracks(row: List[str]) -> Tuple[Feature, Dict, Dict, List]:
    head_tail_feature, attributes, track_attributes, confidence_pairs = _parse_row(row)
    trackId, frame, bounds, fishLength = row_info(row)

    feature = Feature(
        frame,
        bounds,
        attributes=attributes or None,
        fishLength=fishLength if fishLength > 0 else None,
        **head_tail_feature,
    )

    # Pass the rest of the unchanged info through as well
    return feature, attributes, track_attributes, confidence_pairs


def load_csv_as_tracks(file):
    """
    Convert VIAME web CSV to json tracks.
    Expect detections to be in increasing order (either globally or by track).
    """
    rows = (
        b"".join(list(File().download(file, headers=False)()))
        .decode("utf-8")
        .split("\n")
    )
    reader = csv.reader(row for row in rows if (not row.startswith("#") and row))
    tracks = {}

    for row in reader:
        (
            feature,
            attributes,
            track_attributes,
            confidence_pairs,
        ) = _parse_row_for_tracks(row)
        trackId, frame, _, _ = row_info(row)

        if trackId not in tracks:
            tracks[trackId] = Track(frame, frame, trackId)

        track = tracks[trackId]
        track.begin = min(frame, track.begin)
        track.end = max(track.end, frame)
        track.features.append(feature)
        track.confidencePairs = confidence_pairs

        for (key, val) in track_attributes:
            track.attributes[key] = val

    return {trackId: track.asdict() for trackId, track in tracks.items()}


def write_track_to_csv(track: Track, csv_writer):
    def valueToString(value):
        if value is True:
            return "true"
        elif value is False:
            return "false"
        return str(value)

    columns: List[Any] = []
    for feature in track.features:
        columns = [
            track.trackId,
            "",
            feature.frame,
            *feature.bounds,
            track.confidencePairs[-1][1],
            feature.fishLength or -1,
        ]

        for pair in track.confidencePairs:
            columns.extend(list(pair))

        if feature.head and feature.tail:
            columns.extend(
                [
                    f"(kp) head {feature.head[0]} {feature.head[1]}",
                    f"(kp) tail {feature.tail[0]} {feature.tail[1]}",
                ]
            )

        if feature.attributes:
            for key, val in feature.attributes.items():
                columns.append(f"(atr) {key} {valueToString(val)}")

        if track.attributes:
            for key, val in track.attributes.items():
                columns.append(f"(trk-atr) {key} {valueToString(val)}")

        csv_writer.writerow(columns)


def export_tracks_as_csv(file) -> str:
    """
    Export track json to a CSV format.

    file: The detections JSON file
    """

    track_json = json.loads(
        b"".join(list(File().download(file, headers=False)())).decode()
    )

    tracks = {
        # Config kwarg needed to convert lists into tuples
        trackId: from_dict(Track, track, config=Config(cast=[Tuple]))
        for trackId, track in track_json.items()
    }

    with io.StringIO() as csvFile:
        writer = csv.writer(csvFile)

        for track in tracks.values():
            write_track_to_csv(track, writer)

        return csvFile.getvalue()