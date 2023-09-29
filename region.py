"""Region demarcation logic."""
from __future__ import annotations
from dataclasses import dataclass, field


class Node:
    """Tree implementation."""
    def __init__(self, value: tuple[int, int] | int, label: str = '',
                 parent: Node | None = None, children: tuple[tuple[int, str | tuple], ...] = (),):
        self.value = value
        self.label = label
        self.parent = parent
        self.children: list[Node] = []
        for child in children:
            match child:
                case (size, tuple(sub_children)):
                    self.children.append(Node(size, parent=self, children=sub_children))
                case (size, str(sub_label)):
                    self.children.append(Node(size, label=sub_label, parent=self))

    def __str__(self) -> str:
        return str(self.value) + (
            f": <{', '.join(str(child) for child in self.children)}>"
            if self.children else ''
            )


@dataclass(slots=True)
class RegionBlueprint:
    """Template for a region of space [on the screen]."""
    size: tuple[int, int]
    center: tuple[int, int]
    children: list[Node] = field(default_factory=list)
    label: str = ''


def resolve_regions(resolution: tuple[int, int],
                    layout: tuple[tuple[int, str | tuple], ...],
                    border_thickness: int = 0) -> list[RegionBlueprint]:
    """Convert nested tuple representation of regions to defined screen spaces."""
    root = Node(resolution, label="root", children=layout)
    regions: list[RegionBlueprint] = [
        RegionBlueprint(resolution, (resolution[0] // 2, resolution[1] // 2),
                        root.children, "root")
        ]

    def divide_region(region: RegionBlueprint, subdivisions: list[Node], depth: int = 0):
        """Subdivide a region exhaustively using recursion."""
        if not subdivisions:
            return
        # odd depth makes horizontal regions, even depth makes vertical regions
        index: int = depth % 2
        sublengths: list[int] = [node.value for node in subdivisions if isinstance(node.value, int)]
        assert sum(sublengths) == region.size[index], "invalid region sublengths"
        center_offsets = [int((sublength/2)+sum(sublengths[:i]))
                          for i, sublength in enumerate(sublengths)]
        new_centers = [((region.center[0], center_offset)
                        if index else (center_offset, region.center[1]))
                       for center_offset in center_offsets]
        new_sizes = [((region.size[0], sublength) if index else (sublength, region.size[1]))
                     for sublength in sublengths]
        new_regions = [RegionBlueprint(new_sizes[i], new_centers[i],
                                       region.children[i].children, f"{subdivisions[i].label}",)
                       for i in range(len(subdivisions))]
        regions.remove(region)
        regions.extend(new_regions)
        for new_region in new_regions:
            if new_region.children:
                divide_region(new_region, new_region.children, depth+1)

    for region in regions:
        divide_region(region, region.children)
    for region in regions:
        region.size = (region.size[0]-2*border_thickness, region.size[1]-2*border_thickness)

    return regions
