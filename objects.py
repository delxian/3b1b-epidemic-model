"""Functional model elements."""
# pylint: disable=invalid-name,no-member
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from functools import cache, reduce
import random
from time import perf_counter
from typing import Literal

import pygame

from controls import font, TEXT_COLOR, clamp, NumericVariable, Variable
from gradient import Gradient


MAX_INFECTION_DURATION = 60
INFECTION_EVENT_INTERVAL = 3

SPREAD_CHANCE = 0.33  # chance of attempted transmission
INFECTION_CHANCE = 0.5
REINFECTION_CHANCE = 0.1
INFECTED_DISTANCER_CHANCE = 0.7  # social distancing in newly infected
RECOVERED_NONDISTANCER_CHANCE = 0.6  # not social distancing in newly recovered

MORTALITY_CHANCE = 0.1
EARLY_TERMINATION_CHANCE = 0.02  # ending infection period early

TRAVEL_INTERVAL = 2  # time between randomly selected travel
TRAVEL_SPEED_MULTIPLIER = 3  # movement speed traveling between communities

PROXIMITY_COEFFICIENT = 10  # maximum repulsion force multiplier for closer proximity


class Region(pygame.sprite.Sprite):
    """Generic bounding region."""
    border_color = (255, 255, 255)
    padding: int = 20
    show_labels: bool = True
    def __init__(self, size: tuple[int, int], center: tuple[int, int],
                 label_text: str, border_thickness: int = 2):
        super().__init__()
        self.size = size
        self.surf = pygame.Surface(size)
        self.rect = self.surf.get_rect(center=center, size=size)
        self.label_text = label_text
        self.label = font.render(label_text, True, TEXT_COLOR)
        self.border_thickness = border_thickness
        self.active = True

    def update(self):
        """Draw the region."""
        self.surf.fill((0, 0, 0, 0))
        pygame.draw.rect(self.surf, self.border_color,
                         pygame.Rect((0, 0), self.size),
                         self.border_thickness)

    def get_corner(self, corner: Literal["TL", "TR", "BL", "BR"]) -> tuple[int, int]:
        """Get absolute coordinates of a region's corner, accounting for padding."""
        horizontal = (self.padding if corner[1] == "L"
                      else self.size[0] - self.label.get_width() - self.padding)
        vertical = (self.padding if corner[0] == "T"
                    else self.size[1] - self.label.get_height() - self.padding)
        return (horizontal, vertical)

    @property
    def left(self):
        """Left edge of the region, accounting for border."""
        return int(self.rect.center[0]-self.size[0]/2) + self.border_thickness

    @property
    def left_pad(self):
        """Left edge of the region, accounting for border and padding."""
        return self.left + self.padding

    @property
    def top(self):
        """Top edge of the region, accounting for border."""
        return int(self.rect.center[1]-self.size[1]/2) + self.border_thickness

    @property
    def top_pad(self):
        """Top edge of the region, accounting for border and padding."""
        return self.top + self.padding

    @property
    def right(self):
        """Right edge of the region, accounting for border."""
        return self.left + self.size[0] - self.border_thickness

    @property
    def right_pad(self):
        """Right edge of the region, accounting for border and padding."""
        return self.right - self.padding

    @property
    def bottom(self):
        """Bottom edge of the region, accounting for border."""
        return self.top + self.size[1] - self.border_thickness

    @property
    def bottom_pad(self):
        """Bottom edge of the region, accounting for border and padding."""
        return self.bottom - self.padding


class Community(Region):
    """Bounding region for encapsulating and exchanging population."""
    fill_color = (0, 0, 32, 0)
    center_size = 30
    def __init__(self, size: tuple[int, int], center: tuple[int, int],
                 label_text: str, border_thickness: int = 2):
        super().__init__(size, center, label_text, border_thickness)
        self.center_rect = self.surf.get_rect(
            center=(size[0]-self.center_size/2,
                    size[1]-self.center_size/2),
            size=(self.center_size, self.center_size)
            )
        self.absolute_center_rect = pygame.Rect(
            self.left + self.center_rect.left - self.border_thickness,
            self.top + self.center_rect.top - self.border_thickness,
            self.center_size, self.center_size)

    def update(self):
        """Draw the community."""
        super().update()
        self.surf.fill(self.fill_color)
        pygame.draw.rect(self.surf, self.border_color,
                         pygame.Rect((0, 0), self.size),
                         self.border_thickness)
        pygame.draw.rect(self.surf, self.border_color,
                         self.center_rect,
                         self.border_thickness)
        if self.show_labels:
            self.surf.blit(self.label, self.get_corner("TL"))


@dataclass(slots=True)
class Bounds:
    """Class for holding all bounds associated with a person."""
    community: Community
    region: Region


class Person(pygame.sprite.Sprite):
    """Autonomous entity that can move and spread disease."""
    radius = 5
    surf_size = radius*25
    distancing_radius = radius*25
    infection_radius = radius*10
    speed = 120
    id_incrementer = 0
    gradient = Gradient((0, (0, 255, 0)),
                        (100, (255, 255, 0)),
                        (200, (255, 0, 0)),
                        (255, (255, 0, 0)))

    class State(Enum):
        """States that affect the spread of the infection, and their associated colors."""
        SUSCEPTIBLE = (255, 255, 255)
        INFECTED = (255, 0, 0)
        RECOVERED = (100, 255, 100)
        DECEASED = (100, 100, 100)

        def __str__(self) -> str:
            return str(self.name).lower()

    @property
    def color(self):
        """Get the color for the person based on their infection state."""
        return self.state.value

    def __init__(self, bounds: Bounds, distancing_percent: NumericVariable,
                 distancing_strength: NumericVariable, center: tuple[int, int] | None = None,
                 state: State = State.SUSCEPTIBLE):
        super().__init__()
        self.id = Person.id_incrementer
        Person.id_incrementer += 1
        self.surf = pygame.Surface((self.surf_size, self.surf_size), pygame.SRCALPHA)
        self.bounds = bounds
        self.distancing = False
        self.distancing_percent = distancing_percent
        self.randomize_distancing()
        self.distancing_strength = distancing_strength
        self.center = center or (random.randint(self.active_bounds.left + self.radius,
                                                self.active_bounds.right - self.radius),
                                 random.randint(self.active_bounds.top + self.radius,
                                                self.active_bounds.bottom - self.radius))
        self.rect = self.surf.get_rect(center=self.center)
        self.state = state
        self.direction = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        self.infected_start = None
        self.infected_end = None
        self.travel_target: Community | None = None
        self.last_event = 0

    @property
    def active_bounds(self):
        """Return the topmost bounds for the person that is currently active."""
        return self.bounds.community if self.bounds.community.active else self.bounds.region

    def update(self, persons: pygame.sprite.Group, frametime: float,
               direction_toggle: Variable, network_toggle: Variable, distancing_toggle: Variable):
        """Draw the person and handle interactions."""
        self.surf.fill((0, 0, 0, 0))
        center = (int(self.surf_size/2), int(self.surf_size/2))
        if self.state == Person.State.DECEASED:
            pass
        elif self.travel_target:
            self.travel(frametime)
        else:
            self.operate(persons, frametime, direction_toggle, network_toggle, distancing_toggle)
        pygame.draw.circle(self.surf, self.color, center, self.radius)

    def travel(self, frametime: float):
        """Ignore standard operation and navigate towards target community."""
        center = (int(self.surf_size/2), int(self.surf_size/2))
        if not self.travel_target:
            raise RuntimeError("No target community found")
        to_target = -(pygame.Vector2(self.rect.center)
                      - pygame.Vector2(self.travel_target.absolute_center_rect.center))
        if to_target and to_target.length():
            self.direction = to_target.normalize()
        self.rect.move_ip(self.direction.x*self.speed*TRAVEL_SPEED_MULTIPLIER*frametime,
                            self.direction.y*self.speed*TRAVEL_SPEED_MULTIPLIER*frametime)
        pygame.draw.line(self.surf, (255, 255, 0), center, center + self.direction*20)
        # if overlapping center region of target, stop traveling
        if self.travel_target.absolute_center_rect.collidepoint(self.rect.center):
            self.bounds.community = self.travel_target
            self.travel_target = None

    def operate(self, persons: pygame.sprite.Group, frametime: float,
                direction_toggle: Variable, network_toggle: Variable,
                distancing_toggle: Variable):
        """Handle standard operation of the person."""
        center = (int(self.surf_size/2), int(self.surf_size/2))
        if random.random() < 0.5:
            self.direction.rotate_ip(random.randint(-10, 10))
        self.avoid_walls()
        nears = self.get_nearby(persons)
        if self.state == self.State.INFECTED and self.infected_start:
            self.handle_infection(nears)
        if distancing_toggle.value and self.distancing and nears:
            self.social_distance(nears)
            pygame.draw.circle(self.surf, (255, 255, 255, 64),
                                center, self.radius*3, width=1)
        self.rect.move_ip(self.direction.x*self.speed*frametime,
                            self.direction.y*self.speed*frametime)
        self.stay_in_bounds()
        self.display_details(network_toggle, direction_toggle, nears)

    def avoid_walls(self):
        """Change the player's direction when they encounter a wall."""
        adjusted = False
        if abs(self.rect.center[0] - self.active_bounds.left) < 10:
            self.direction = pygame.Vector2(1, 0)
            adjusted = True
        elif abs(self.rect.center[0] - self.active_bounds.right) < 10:
            self.direction = pygame.Vector2(-1, 0)
            adjusted = True
        elif abs(self.rect.center[1] - self.active_bounds.top) < 10:
            self.direction = pygame.Vector2(0, 1)
            adjusted = True
        elif abs(self.rect.center[1] - self.active_bounds.bottom) < 10:
            self.direction = pygame.Vector2(0, -1)
            adjusted = True
        if adjusted and random.random() < 0.5:
            self.direction.rotate_ip(random.randint(-80, 80))

    def get_nearby(self, persons: pygame.sprite.Group) -> list[Person]:
        """Get nearby people within distancing radius."""
        others: list[Person] = persons.sprites()
        nears = [other for other in others  # optimize for next step
                if self.rect.colliderect(other.rect) and
                other.state != Person.State.DECEASED and
                not other.travel_target and
                self.active_bounds == other.active_bounds]
        return [other for other in nears   # gather people within distance radius?
                if (pygame.Vector2(self.rect.center)
                    - pygame.Vector2(other.rect.center)).length() < self.distancing_radius]

    def handle_infection(self, nears: list[Person]):
        """Handle infection events."""
        if not self.infected_start:
            raise RuntimeError("Infection start time not found")
        if perf_counter()-self.infected_start >= MAX_INFECTION_DURATION:
            self.end_infection()
        if (not self.travel_target and
            perf_counter()-self.last_event >= INFECTION_EVENT_INTERVAL):
            if random.random() < SPREAD_CHANCE:
                center = (int(self.surf_size/2), int(self.surf_size/2))
                self.spread(nears, center)
            if random.random() < EARLY_TERMINATION_CHANCE:
                self.end_infection()
            self.last_event = perf_counter()

    def end_infection(self):
        """Decide whether the person recovers or dies according to mortality chance."""
        self.infected_end = perf_counter()
        if random.random() <= MORTALITY_CHANCE:
            self.die()
        else:
            self.recover()

    def recover(self):
        """Mark the player as recovered and end their infection."""
        self.state = Person.State.RECOVERED
        if self.infected_end and self.infected_start:
            print(f"Person {self.id} recovered " \
                  f"({round(self.infected_end-self.infected_start)}s)")
        self.distancing = random.random() <= RECOVERED_NONDISTANCER_CHANCE

    def die(self):
        """Mark the person as deceased. They will be visible but no longer move or interact."""
        self.state = Person.State.DECEASED
        if self.infected_end and self.infected_start:
            print(f"Person {self.id} died ({round(self.infected_end-self.infected_start)}s)")

    def social_distance(self, nears: list[Person]):
        """Change the direction of the person to avoid those nearby."""
        forces = [(diff_vector * PROXIMITY_COEFFICIENT
                   * (1 - (diff_vector.length() / self.distancing_radius))**2)
                  for other in nears
                  if (diff_vector := pygame.Vector2(self.rect.center)
                      - pygame.Vector2(other.rect.center)).length()]
        if forces:
            force: pygame.Vector2 = reduce(lambda a, b: a + b, forces)/len(forces)
            if force and force.length():
                force = force.normalize()
            intermediate = self.direction+force*self.distancing_strength.value
            self.direction = intermediate.normalize() if intermediate.length() else self.direction

    def spread(self, nears: list[Person], center):
        """Attempt to transmit the infection from the person, drawing the infection radius."""
        pygame.draw.circle(self.surf, (255, 0, 0, 64),
                           center, self.infection_radius)
        nears = [other for other in nears
                 if (pygame.Vector2(self.rect.center)
                     - pygame.Vector2(other.rect.center)).length() < self.infection_radius]
        for other in nears:
            chance = {
                Person.State.SUSCEPTIBLE: INFECTION_CHANCE,
                Person.State.RECOVERED: REINFECTION_CHANCE,
                }.get(other.state, 0)
            if other is not self and random.random() < chance:
                other.get_infected()

    def get_infected(self):
        """Mark the person as infected, allowing them to spread the infection."""
        self.infected_start = perf_counter()
        self.infected_end = None
        print(f"Person {self.id} infected")
        self.last_event = max(0, perf_counter()-random.random()*5)
        self.state = Person.State.INFECTED
        self.distancing = random.random() <= INFECTED_DISTANCER_CHANCE

    def stay_in_bounds(self):
        """Force the player's location to stay within active bounds."""
        self.rect.center = (
            int(clamp(self.rect.center[0],
                    self.active_bounds.left + self.radius,
                    self.active_bounds.right - self.radius)),
            int(clamp(self.rect.center[1],
                    self.active_bounds.top + self.radius,
                    self.active_bounds.bottom - self.radius))
            )

    def display_details(self, network_toggle: Variable,
                        direction_toggle: Variable, nears: list[Person]):
        """Display extra per-person visual information."""
        center = (int(self.surf_size/2), int(self.surf_size/2))
        if network_toggle.value:
            for other in nears:
                if (to_other := (pygame.Vector2(self.rect.center)
                                    - pygame.Vector2(other.rect.center))):
                    intensity = self.get_intensity(to_other.length(), self.distancing_radius)
                    color = self.gradient.get_color(intensity)
                    pygame.draw.line(self.surf, (*color, intensity),
                                        center, center - to_other/2)
        if direction_toggle.value:
            pygame.draw.line(self.surf, (0, 255, 255), center, center + self.direction*20)

    def randomize_distancing(self):
        """Randomize whether the person social distances or not based on the variable."""
        self.distancing = random.random() <= self.distancing_percent.value/100

    def start_traveling(self, target: Community):
        """Assign a community for the person to travel towards."""
        self.travel_target = target

    @staticmethod
    @cache
    def get_intensity(distance: int | float, radius: int):
        """Get color intensity value based on proximity of those nearby."""
        return abs(int(255*(1-(min(distance, radius)/radius))))


class Chart(pygame.sprite.Sprite):
    """Stacked area chart for population breakdown."""
    update_interval = 1  # interval in seconds to update the chart
    snapshot_width = 1  # width in pixels of each update
    def __init__(self, size: tuple[int, int], center: tuple[int, int],
                 values: tuple[tuple[str, tuple[int, int, int]],...]):
        super().__init__()
        self.surf = pygame.Surface(size)
        self.rect = self.surf.get_rect(center=center, size=size)
        self.data: list = [(0.0, 0.0, 1.0, 0.0)]*size[0]
        self.values = values  # values for chart from bottom to top
        self.last_update = perf_counter()
        self.event_marker: tuple[int, int, int] | None = None

    def update(self, data: dict[str, int]):
        """Draw the chart."""
        chart_width, chart_height = self.surf.get_size()
        # store new data
        if perf_counter() - self.last_update >= self.update_interval:
            for _ in range(self.snapshot_width):
                if self.event_marker:
                    self.data.append(self.event_marker)
                    self.event_marker = None
                else:
                    total = sum(data.values())
                    entry = tuple(data[value[0]]/total for value in self.values)
                    self.data.append(entry)  # type: ignore
                    if (overflow := len(self.data) - chart_width):
                        self.data = self.data[overflow:]
            self.last_update = perf_counter()
        # draw existing data
        for i in range(chart_width):
            if all(isinstance(member, int) for member in self.data[i]):
                pygame.draw.line(self.surf, self.data[i], (i, chart_height), (i, 0))
            else:
                vertical_start = 0
                pygame.draw.line(self.surf, (255, 255, 255), (i, chart_height), (i, 0))
                for j, value in enumerate(self.data[i]):
                    length = round(value*chart_height)
                    color = self.values[j][1]
                    start = (i, chart_height-vertical_start)
                    end = (i, chart_height-vertical_start-length)
                    if end[1] == 1:
                        end = (i, 0)  # handle stray pixel from rounding errors
                    pygame.draw.line(self.surf, color, start, end)
                    vertical_start += length

    def mark_event(self, color: tuple[int, int, int]):
        """Add a colored event marker to plot on the chart."""
        self.event_marker = color
