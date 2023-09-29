"""Color gradient with color stops."""
from functools import cache
from itertools import pairwise


RGBTuple = tuple[int, int, int]


class Gradient:
    """Handle gradient transitions."""
    def __init__(self, *args: tuple[int, RGBTuple]):
        self.colors: tuple[tuple[int, RGBTuple], ...] = tuple(sorted(args))

    def get_color(self, value: int | float) -> tuple[int, int, int]:
        """Get a color for a particular value based on color stop configuration."""
        active_lower, active_upper = next((lower, upper) for lower, upper in pairwise(self.colors)
                                          if value in range(lower[0], upper[0]+1))
        return self._process_value(active_lower, active_upper, value)

    @staticmethod
    @cache
    def _process_value(lower: tuple[int, RGBTuple],
                       upper: tuple[int, RGBTuple], value: int | float):
        """Get color value for a given position between two color stops."""
        min_value, lower_color = lower
        max_value, upper_color = upper
        percentage = (value - min_value)/(max_value - min_value)
        delta = (upper_color[0]-lower_color[0],
                 upper_color[1]-lower_color[1],
                 upper_color[2]-lower_color[2])
        return (int(lower_color[0]+delta[0]*percentage),
                int(lower_color[1]+delta[1]*percentage),
                int(lower_color[2]+delta[2]*percentage))
