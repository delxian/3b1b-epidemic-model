"""Execution of the model."""
# pylint: disable=no-name-in-module,no-member,invalid-name,redefined-outer-name
from __future__ import annotations
from itertools import cycle
import random
from time import perf_counter
from typing import Protocol

import pygame
from pygame.locals import KEYDOWN, QUIT, K_ESCAPE, MOUSEBUTTONDOWN, MOUSEBUTTONUP

from controls import font, TEXT_COLOR, Button, BooleanVariable, Checkbox, NumericVariable, Slider
from objects import TRAVEL_INTERVAL, Region, Community, Bounds, Person, Chart
from region import RegionBlueprint, resolve_regions

# https://www.youtube.com/watch?v=gxAaO2rsdIs


pygame.init()

SCREEN_WIDTH, SCREEN_HEIGHT = (1920, 1080)
FULL_WIDTH, FULL_HEIGHT = (SCREEN_WIDTH*5, SCREEN_HEIGHT*5)
SETTINGS_WIDTH = 450
FRAMERATE = 120
DEFAULT_PERSON_COUNT = 200

BACKGROUND_COLOR = (0, 0, 0)

DISTANCING_EVENT_COLOR = (0, 255, 255)
TRAVELING_EVENT_COLOR = (255, 128, 0)

ADD_TEN_PEOPLE = pygame.USEREVENT + 1
REMOVE_TEN_PEOPLE = pygame.USEREVENT + 2
INFECT_ONE_PERSON = pygame.USEREVENT + 3
RANDOMIZE_DISTANCERS = pygame.USEREVENT + 4
RANDOMIZE_FORCE_DISPLAY = pygame.USEREVENT + 5
TRAVEL_ONE_PERSON = pygame.USEREVENT + 6
pygame.time.set_timer(TRAVEL_ONE_PERSON, int(1000*TRAVEL_INTERVAL))

ADJUST_DISTANCING_PERCENT = pygame.USEREVENT + 7


def set_up_regions(
        new_regions: list[RegionBlueprint]
        ) -> tuple[pygame.sprite.Group, dict[str, Region]]:
    """Generate and organize regions in pygame."""
    regions, region_dict = pygame.sprite.Group(), {}
    for blueprint in new_regions:
        region = Region(blueprint.size, blueprint.center, blueprint.label)
        regions.add(region)
        region_dict[blueprint.label] = region
    return (regions, region_dict)

def set_up_communities(new_communities: list[RegionBlueprint],
                       x_offset: int) -> tuple[pygame.sprite.Group, dict[str, Community]]:
    """Generate and organize communities in pygame."""
    communities, community_dict = pygame.sprite.Group(), {}
    for blueprint in new_communities:
        center = (blueprint.center[0]+10+x_offset, blueprint.center[1]+10)
        community = Community(blueprint.size, center, blueprint.label)
        communities.add(community)
        community_dict[blueprint.label] = community
    return (communities, community_dict)

def set_up_buttons(new_buttons: tuple[tuple[str, int],...]) -> pygame.sprite.Group:
    """Generate and organize buttons in pygame."""
    buttons = pygame.sprite.Group()
    for i, (label, event) in enumerate(new_buttons):
        buttons.add(
            Button(label,
                   (settings.left_pad,
                    settings.bottom_pad - font.get_height()
                    - 50*(len(new_buttons)-1-i)),
                   event)
            )
    return buttons

def set_up_checkboxes(
        new_checkboxes: tuple[tuple[str, BooleanVariable],...]
        ) -> pygame.sprite.Group:
    """Generate and organize checkboxes in pygame."""
    checkboxes = pygame.sprite.Group()
    for i, (label, variable) in enumerate(new_checkboxes):
        checkboxes.add(
            Checkbox(label,
                     (settings.left_pad,
                      settings.top_pad + int(Checkbox.width*0.5)
                      + int((Checkbox.width+settings.padding)*i)),
                     variable, variable.value)
            )
    return checkboxes


# divide screenspace into field and settings regions
new_regions: list[RegionBlueprint] = resolve_regions(
    (SCREEN_WIDTH, SCREEN_HEIGHT),
    ((SCREEN_WIDTH-SETTINGS_WIDTH, "Field"), (SETTINGS_WIDTH, "Settings")),
    border_thickness=10
    )
regions, region_dict = set_up_regions(new_regions)
field, settings = region_dict["Field"], region_dict["Settings"]

# create a square of maximum size centered in the field
field_square_width: int = field.size[1]
field_square_x_offset = int((field.size[0]-field.size[1])/2)
# split into 4 squares
new_communities: list[RegionBlueprint] = resolve_regions(
    (field_square_width, field_square_width),
    ((field_square_width // 2,
      ((field_square_width // 2, "TL"), (field_square_width // 2, "BL"))),
     (field_square_width // 2,
      ((field_square_width // 2, "TR"), (field_square_width // 2, "BR")))),
    border_thickness=10
    )
communities, community_dict = set_up_communities(new_communities, field_square_x_offset)
top_left, bottom_left, top_right, bottom_right = (
    community_dict["TL"], community_dict["BL"], community_dict["TR"], community_dict["BR"])
community_cycler = cycle((top_left, top_right, bottom_right, bottom_left))

persons = pygame.sprite.Group()
distancing_percent = NumericVariable("distancing percent", 100, ADJUST_DISTANCING_PERCENT)
distancing_strength = NumericVariable("distancing strength", 1)
for _ in range(DEFAULT_PERSON_COUNT):
    persons.add(Person(Bounds(next(community_cycler), field),
                       distancing_percent, distancing_strength))

charts = pygame.sprite.Group()
chart_size = settings.right_pad-settings.left_pad
chart_center = (int((settings.left_pad+settings.right_pad)/2),
                int((settings.bottom_pad+settings.top_pad)/2)-50)
chart_values = (("infected", (255, 0, 0)),
                ("recovered", (100, 255, 100)),
                ("susceptible", (255, 255, 255)),
                ("deceased", (100, 100, 100)))
main_chart = Chart((chart_size, chart_size), chart_center, chart_values)
charts.add(main_chart)

new_buttons = (("Add 10 People", ADD_TEN_PEOPLE),
               ("Remove 10 People", REMOVE_TEN_PEOPLE),
               ("Infect 1 Person", INFECT_ONE_PERSON),
               ("Randomize Distancers", RANDOMIZE_DISTANCERS),)
buttons = set_up_buttons(new_buttons)

directions_toggle = BooleanVariable("directions", False)
network_toggle = BooleanVariable("network", False)
distancing_toggle = BooleanVariable("distancing", False)
communities_toggle = BooleanVariable("communities", True)
traveling_toggle = BooleanVariable("travel", True)
new_checkboxes = (("Show Directions", directions_toggle),
                  ("Show Network", network_toggle),
                  ("Social Distance", distancing_toggle),
                  ("Enable Communities", communities_toggle),
                  ("Enable Traveling", traveling_toggle))
checkboxes = set_up_checkboxes(new_checkboxes)

sliders = pygame.sprite.Group()
sliders.add(Slider("Distancing %",
                   (settings.left_pad, settings.bottom-font.get_height()-300),
                   distancing_percent, (0, 100)))
sliders.add(Slider("Distancing Strength",
                   (settings.left_pad, settings.bottom-font.get_height()-260),
                   distancing_strength, (0, 3), decimals=2))


class Blitable(Protocol):
    """Sprite protocol to circumvent `pygame.sprite.Group()` type hinting."""
    surf: pygame.Surface
    rect: pygame.Rect


class Point:
    """Binding for coordinate pair."""
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def move(self, x: int, y: int) -> Point:
        """Return a new `Point` with adjusted `x` and `y` coordinates."""
        return Point(self.x + x, self.y + y)

    @property
    def tuple(self) -> tuple[int, int]:
        """Get a tuple of the point's coordinates."""
        return (self.x, self.y)


clock, frametime, start_time = pygame.time.Clock(), 0, perf_counter()
running, mouse_down = True, (None, None)
canvas = pygame.display.set_mode((FULL_WIDTH, FULL_HEIGHT))
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

while running:
    mouse_buttons = pygame.mouse.get_pressed()
    mouse_position = pygame.mouse.get_pos()

    # handle events
    for event in pygame.event.get():
        if event.type == KEYDOWN and event.key == K_ESCAPE:
            running = False
        elif event.type == MOUSEBUTTONDOWN:
            mouse_down = mouse_position
            if event.button == 1:
                if field.rect.collidepoint(*mouse_position):
                    if communities_toggle.value:
                        if (hovered_community := next(
                            (community for community in communities
                             if community.rect.collidepoint(*mouse_position)), None)):
                            community = hovered_community
                    persons.add(
                        Person(Bounds(community, field),
                               distancing_percent=distancing_percent,
                               distancing_strength=distancing_strength,
                               center=mouse_position)
                        )
                for checkbox in checkboxes:
                    checkbox: Checkbox
                    if checkbox.rect.collidepoint(*mouse_position):
                        checkbox.toggle()
                        if checkbox.variable is distancing_toggle:
                            main_chart.mark_event(DISTANCING_EVENT_COLOR)
                        elif checkbox.variable is traveling_toggle:
                            main_chart.mark_event(TRAVELING_EVENT_COLOR)
                for button in buttons:
                    button: Button
                    if button.rect.collidepoint(*mouse_position):
                        pygame.event.post(pygame.event.Event(button.event))
        elif event.type == MOUSEBUTTONUP:
            mouse_down = (None, None)
        elif event.type == ADD_TEN_PEOPLE:
            for _ in range(10):
                persons.add(
                    Person(Bounds(next(community_cycler), field),
                           distancing_percent=distancing_percent,
                           distancing_strength=distancing_strength)
                    )
        elif event.type == REMOVE_TEN_PEOPLE:
            for _ in range(min(len(persons), 10)):
                if communities_toggle.value:
                    while True:
                        community = next(community_cycler)
                        remove_pool = [person for person in persons
                                       if person.active_bounds == community]
                        if remove_pool:
                            break
                else:
                    remove_pool = persons.sprites()
                person = random.choice(remove_pool)
                person.kill()
        elif event.type == INFECT_ONE_PERSON:
            infectible = [person for person in persons
                          if person.state in {Person.State.SUSCEPTIBLE, Person.State.RECOVERED}]
            person: Person = random.choice(infectible)
            person.get_infected()
        elif event.type == RANDOMIZE_DISTANCERS:
            for person in persons:
                person.distancing = False
            target = int(distancing_percent.value/100 * len(persons))
            new_distancers = random.sample(persons.sprites(), k=target)
            for person in new_distancers:
                person.distancing = True
        elif event.type == TRAVEL_ONE_PERSON:
            if communities_toggle.value and traveling_toggle.value:
                person = random.choice(persons.sprites())
                target_community: Community = random.choice(
                    [community for community in communities
                    if community is not person.bounds.community]
                    )
                person.start_traveling(target_community)
        elif event.type == ADJUST_DISTANCING_PERCENT:
            target = int(distancing_percent.value/100 * len(persons))
            distancers = [person for person in persons if person.distancing]
            non_distancers = [person for person in persons if not person.distancing]
            if (diff := target - len(distancers)):
                population, distancing = ((non_distancers, True) if diff > 0
                                          else (distancers, False))
                change_distancing: list[Person] = random.sample(population, k=abs(diff))
                for person in change_distancing:
                    person.distancing = distancing
            distancing_percent.resolve_diff()
        elif event.type == QUIT:
            running = False

    # update sprites
    regions.update()
    for community in communities:
        community: Community
        community.active = communities_toggle.value
        community.update()
    persons.update(persons, frametime, directions_toggle, network_toggle, distancing_toggle)
    chart_data = {str(state): len([person for person in persons if person.state == state])
                  for state in Person.State}
    charts.update(chart_data)  # data = dict of counts of infection states
    buttons.update(mouse_buttons, mouse_position)
    checkboxes.update()
    sliders.update(mouse_position, mouse_down)

    # draw bg
    canvas.fill(BACKGROUND_COLOR)

    # draw sprites
    labels = (("timer", round(perf_counter()-start_time, 1)),
              ("people", len(persons)),
              ("distancers", len([person for person in persons if person.distancing])),
              ("susceptible", len([person for person in persons
                                   if person.state == Person.State.SUSCEPTIBLE])),
              ("infected", len([person for person in persons
                                if person.state == Person.State.INFECTED])),
              ("recovered", len([person for person in persons
                                 if person.state == Person.State.RECOVERED])),
              ("deceased", len([person for person in persons
                                if person.state == Person.State.DECEASED])))
    for i, data in enumerate(labels):
        label = font.render(f"{data[0]}: {str(data[1])}", True, TEXT_COLOR)
        field.surf.blit(label, Point(*field.get_corner("TL")).move(0, 40*i).tuple)
    mouse_label = font.render(f"({mouse_position[0]}, {mouse_position[1]})", True, TEXT_COLOR)
    field.surf.blit(mouse_label, Point(*field.get_corner("BL")).move(0, 0).tuple)

    groups = [regions, persons, charts, buttons, checkboxes, sliders]
    if communities_toggle.value:
        groups.insert(1, communities)
    for group in groups:
        for sprite in group:
            sprite: Blitable
            canvas.blit(sprite.surf, sprite.rect)
    scaled = pygame.transform.scale(canvas, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled, scaled.get_rect())

    pygame.display.flip()
    frametime = float(clock.tick(FRAMERATE)/1000)
