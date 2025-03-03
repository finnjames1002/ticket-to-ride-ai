from collections import deque
from dataclasses import dataclass
import time
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum
import random
import copy
from mcts import MCTS
from console import LiveConsole
#from graph import TicketToRideVisualizer
from fw import FloydWarshall
from randomAgent import RandomAgent

class Color(Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    BLACK = "black"
    ORANGE = "orange"
    WHITE = "white"
    PINK = "pink"
    GRAY = "gray"
    WILD = "wild"

# Disjointed set for efficient connectivity checking
class UnionFind:
    def __init__(self, cities):
        self.parent = {city: city for city in cities}
        self.rank = {city: 1 for city in cities}

    def find(self, city):
        if self.parent[city] != city:
            self.parent[city] = self.find(self.parent[city])  # Path compression
        return self.parent[city]

    def union(self, city1, city2):
        root1 = self.find(city1)
        root2 = self.find(city2)
        if root1 != root2:
            if self.rank[root1] > self.rank[root2]:
                self.parent[root2] = root1
            elif self.rank[root1] < self.rank[root2]:
                self.parent[root1] = root2
            else:
                self.parent[root2] = root1
                self.rank[root1] += 1

    def is_connected(self, city1, city2):
        return self.find(city1) == self.find(city2)
    
# Destination class to store destination cities and points
@dataclass
class Destination:
    city1: str
    city2: str
    points: int

# Player class to store player information
@dataclass
class Player:
    name: str
    remaining_trains: int = 45
    train_cards: Dict[Color, int] = None
    destinations: List[Destination] = None
    claimed_connections: List[Tuple[str, str, Color]] = None
    claimed_cities: Set[str] = None
    points: int = 0
    turn: int = 1
    uf: UnionFind = None
    
    def __post_init__(self):
        if self.train_cards is None:
            self.train_cards = {color: 0 for color in Color}
        if self.destinations is None:
            self.destinations = []
        if self.claimed_connections is None:
            self.claimed_connections = []
        if self.claimed_cities is None:
            self.claimed_cities = set()
        
    def getTrainCards(self) -> List[Tuple[Color, int]]:
        return [(color, count) for color, count in self.train_cards.items() if count > 0]
    
    def getClaimedCity(self,city: str) -> bool:
        return city in self.claimed_cities

@dataclass
class Route:
    length: int
    color: Color
    claimed_by: str = None

    def claim(self, player: str):
        self.claimed_by = player

    def is_claimed(self) -> bool:
        return self.claimed_by is not None
    
# Handles the game state, including the board, players, current player index, score, train deck, destination deck, and face-up cards
class GameState:
    def __init__(self):
        self.routes = {}
        self.players: List[Player] = []
        self.current_player_idx: int = 0
        self.current_player: Player = None
        self.score: Dict[str, int] = {}
        self.train_deck: List[Color] = []
        self.destination_deck: List[Destination] = []
        self.face_up_cards: List[Color] = []
        #self.visualizer = TicketToRideVisualizer(self)
        self.fw = None    
        self.update = None
        self._unclaimed_routes_cache = None    # Cache for unclaimed routes
        self._cache_valid = False   # Flag to indicate if cache needs update
        

    def init(self):
        self.initialise_destination_deck()
        self.initialise_routes()
        
        self.fw = FloydWarshall(self.routes)
        # Add 12 of each color (excluding wild) and 14 wild cards
        self.setup_train_deck()
        # Draw initial face-up cards
        self.face_up_cards = [self.train_deck.pop() for _ in range(5)]
        self.current_player = self.players[self.current_player_idx]

    def init_uf(self):
        for player in self.players:
            player.uf = UnionFind(self.routes.keys())

    def initialise_destination_deck(self):
        # Add destination tickets to the deck
        destinations = [
            Destination("Denver", "El Paso", 4),
            Destination("Kansas City", "Houston", 5),
            Destination("New York", "Atlanta", 6),
            Destination("Calgary", "Salt Lake City", 7),
            Destination("Chicago", "New Orleans", 7),
            Destination("Duluth", "Houston", 8),
            Destination("Helena", "Los Angeles", 8),
            Destination("Sault St. Marie", "Nashville", 8),
            Destination("Sault St. Marie", "Oklahoma City", 9),
            Destination("Chicago", "Santa Fe", 9),
            Destination("Montreal", "Atlanta", 9),
            Destination("Seattle", "Los Angeles", 9),
            Destination("Duluth", "El Paso", 10),
            Destination("Toronto", "Miami", 10),
            Destination("Dallas", "New York", 11),
            Destination("Denver", "Pittsburgh", 11),
            Destination("Portland", "Phoenix", 11),
            Destination("Winnipeg", "Little Rock", 11),
            Destination("Boston", "Miami", 12),
            Destination("Winnipeg", "Houston", 12),
            Destination("Calgary", "Phoenix", 13),
            Destination("Montreal", "New Orleans", 13),
            Destination("Vancouver", "Santa Fe", 13),
            Destination("Los Angeles", "Chicago", 16),
            Destination("Portland", "Nashville", 17),
            Destination("San Francisco", "Atlanta", 17),
            Destination("Los Angeles", "Miami", 20),
            Destination("Vancouver", "Montreal", 20),
            Destination("Los Angeles", "New York", 21),
            Destination("Seattle", "New York", 22)
        ]
        self.destination_deck = destinations
        random.shuffle(self.destination_deck)
        
    def initialise_routes(self):
        self.routes = {
            "New York": {
                "Boston": [
                    Route(length=2, color=Color.YELLOW),
                    Route(length=2, color=Color.RED)
                ],
                "Pittsburgh": [
                    Route(length=2, color=Color.WHITE),
                    Route(length=2, color=Color.GREEN)
                ],
                "Washington": [
                    Route(length=2, color=Color.ORANGE),
                    Route(length=2, color=Color.BLACK)
                ],
                "Montreal": [
                    Route(length=3, color=Color.BLUE)
                ]
            },
            "Boston": {
                "New York": [
                    Route(length=2, color=Color.YELLOW),
                    Route(length=2, color=Color.RED)
                ],
                "Montreal": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Pittsburgh": {
                "New York": [
                    Route(length=2, color=Color.WHITE),
                    Route(length=2, color=Color.GREEN)
                ],
                "Washington": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Raleigh": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Nashville": [
                    Route(length=4, color=Color.YELLOW)
                ],
                "Saint Louis": [
                    Route(length=5, color=Color.GREEN)
                ],
                "Toronto": [
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Washington": {
                "New York": [
                    Route(length=2, color=Color.ORANGE),
                    Route(length=2, color=Color.BLACK)
                ],
                "Raleigh": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Pittsburgh": [
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Montreal": {
                "Boston": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Toronto": [
                    Route(length=3, color=Color.GRAY)
                ],
                "New York": [
                    Route(length=3, color=Color.BLUE)
                ],
                "Sault St. Marie": [
                    Route(length=5, color=Color.BLACK)
                ]
            },
            "Toronto": {
                "Montreal": [
                    Route(length=3, color=Color.GRAY)
                ],
                "Pittsburgh": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Chicago": [
                    Route(length=4, color=Color.WHITE)
                ],
                "Sault St. Marie": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Duluth": [
                    Route(length=6, color=Color.PINK)
                ]
            },
            "Raleigh": {
                "Washington": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Pittsburgh": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Charleston": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Atlanta": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Nashville": [
                    Route(length=3, color=Color.BLACK)
                ]
            },
            "Charleston": {
                "Raleigh": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Atlanta": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Miami": [
                    Route(length=4, color=Color.PINK)
                ]
            },
            "Atlanta": {
                "Raleigh": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Charleston": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Nashville": [
                    Route(length=1, color=Color.GRAY)
                ],
                "Miami": [
                    Route(length=5, color=Color.BLUE)
                ],
                "New Orleans": [
                    Route(length=4, color=Color.YELLOW),
                    Route(length=4, color=Color.ORANGE)
                ]
            },
            "Nashville": {
                "Pittsburgh": [
                    Route(length=4, color=Color.YELLOW)
                ],
                "Atlanta": [
                    Route(length=1, color=Color.GRAY)
                ],
                "Saint Louis": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Raleigh": [
                    Route(length=3, color=Color.BLACK)
                ],
                "Little Rock": [
                    Route(length=3, color=Color.WHITE)
                ]
            },
            "Saint Louis": {
                "Pittsburgh": [
                    Route(length=5, color=Color.GREEN)
                ],
                "Nashville": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Kansas City": [
                    Route(length=2, color=Color.BLUE),
                    Route(length=2, color=Color.PINK)
                ],
                "Chicago": [
                    Route(length=2, color=Color.GREEN),
                    Route(length=2, color=Color.WHITE)
                ],
                "Little Rock": [
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Chicago": {
                "Saint Louis": [
                    Route(length=2, color=Color.GREEN),
                    Route(length=2, color=Color.WHITE)
                ],
                "Pittsburgh": [
                    Route(length=3, color=Color.ORANGE),
                    Route(length=3, color=Color.BLACK)
                ],
                "Toronto": [
                    Route(length=4, color=Color.WHITE)
                ],
                "Omaha": [
                    Route(length=4, color=Color.BLUE)
                ],
                "Duluth": [
                    Route(length=3, color=Color.RED)
                ]
            },
            "Kansas City": {
                "Saint Louis": [
                    Route(length=2, color=Color.BLUE),
                    Route(length=2, color=Color.PINK)
                ],
                "Oklahoma City": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Denver": [
                    Route(length=4, color=Color.BLACK),
                    Route(length=4, color=Color.ORANGE)
                ],
                "Omaha": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ]
            },
            "Oklahoma City": {
                "Kansas City": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Dallas": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Little Rock": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Santa Fe": [
                    Route(length=3, color=Color.BLUE)
                ],
                "El Paso": [
                    Route(length=5, color=Color.YELLOW)
                ],
                "Denver": [
                    Route(length=4, color=Color.RED)
                ]
            },
            "Dallas": {
                "Oklahoma City": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Little Rock": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Houston": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ],
                "El Paso": [
                    Route(length=4, color=Color.RED)
                ]
            },
            "Little Rock": {
                "Oklahoma City": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Dallas": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Saint Louis": [
                    Route(length=2, color=Color.GRAY)
                ],
                "New Orleans": [
                    Route(length=3, color=Color.GREEN)
                ],
                "Nashville": [
                    Route(length=3, color=Color.WHITE)
                ]
            },
            "Houston": {
                "Dallas": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ],
                "New Orleans": [
                    Route(length=2, color=Color.GRAY)
                ],
                "El Paso": [
                    Route(length=6, color=Color.GREEN)
                ]
            },
            "New Orleans": {
                "Little Rock": [
                    Route(length=3, color=Color.GREEN)
                ],
                "Houston": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Miami": [
                    Route(length=6, color=Color.RED)
                ],
                "Atlanta": [
                    Route(length=4, color=Color.YELLOW),
                    Route(length=4, color=Color.ORANGE)
                ]
            },
            "Miami": {
                "Atlanta": [
                    Route(length=5, color=Color.BLUE)
                ],
                "New Orleans": [
                    Route(length=6, color=Color.RED)
                ],
                "Charleston": [
                    Route(length=4, color=Color.PINK)
                ]
            },
            "Denver": {
                "Kansas City": [
                    Route(length=4, color=Color.BLACK),
                    Route(length=4, color=Color.ORANGE)
                ],
                "Oklahoma City": [
                    Route(length=4, color=Color.RED)
                ],
                "Santa Fe": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Phoenix": [
                    Route(length=5, color=Color.WHITE)
                ],
                "Salt Lake City": [
                    Route(length=3, color=Color.RED),
                    Route(length=3, color=Color.YELLOW)
                ],
                "Helena": [
                    Route(length=4, color=Color.GREEN)
                ],
                "Omaha": [
                    Route(length=4, color=Color.PINK)
                ]
            },
            "Santa Fe": {
                "Denver": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Oklahoma City": [
                    Route(length=3, color=Color.BLUE)
                ],
                "Phoenix": [
                    Route(length=3, color=Color.GRAY)
                ],
                "El Paso": [
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Phoenix": {
                "Santa Fe": [
                    Route(length=3, color=Color.GRAY)
                ],
                "Denver": [
                    Route(length=5, color=Color.WHITE)
                ],
                "Los Angeles": [
                    Route(length=3, color=Color.GRAY)
                ],
                "El Paso": [
                    Route(length=3, color=Color.GRAY)
                ]
            },
            "El Paso": {
                "Phoenix": [
                    Route(length=3, color=Color.GRAY)
                ],
                "Santa Fe": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Houston": [
                    Route(length=6, color=Color.GREEN)
                ],
                "Dallas": [
                    Route(length=4, color=Color.RED)
                ],
                "Oklahoma City": [
                    Route(length=5, color=Color.YELLOW)
                ],
                "Los Angeles": [
                    Route(length=6, color=Color.BLACK)
                ]
            },
            "Salt Lake City": {
                "Denver": [
                    Route(length=3, color=Color.RED),
                    Route(length=3, color=Color.YELLOW)
                ],
                "Helena": [
                    Route(length=3, color=Color.PINK)
                ],
                "Las Vegas": [
                    Route(length=3, color=Color.ORANGE)
                ],
                "San Francisco": [
                    Route(length=5, color=Color.ORANGE),
                    Route(length=5, color=Color.WHITE)
                ],
                "Portland": [
                    Route(length=6, color=Color.BLUE)
                ]
            },
            "Helena": {
                "Salt Lake City": [
                    Route(length=3, color=Color.PINK)
                ],
                "Denver": [
                    Route(length=4, color=Color.GREEN)
                ],
                "Omaha": [
                    Route(length=5, color=Color.RED)
                ],
                "Duluth": [
                    Route(length=6, color=Color.ORANGE)
                ],
                "Winnipeg": [
                    Route(length=4, color=Color.BLUE)
                ],
                "Calgary": [
                    Route(length=4, color=Color.GRAY)
                ],
                "Seattle": [
                    Route(length=6, color=Color.YELLOW)
                ]
            },
            "Omaha": {
                "Chicago": [
                    Route(length=4, color=Color.BLUE)
                ],
                "Kansas City": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ],
                "Denver": [
                    Route(length=4, color=Color.PINK)
                ],
                "Helena": [
                    Route(length=5, color=Color.RED)
                ],
                "Duluth": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Duluth": {
                "Chicago": [
                    Route(length=3, color=Color.RED)
                ],
                "Omaha": [
                    Route(length=2, color=Color.GRAY),
                    Route(length=2, color=Color.GRAY)
                ],
                "Helena": [
                    Route(length=6, color=Color.ORANGE)
                ],
                "Winnipeg": [
                    Route(length=4, color=Color.BLACK)
                ],
                "Sault St. Marie": [
                    Route(length=3, color=Color.GRAY)
                ],
                "Toronto": [
                    Route(length=6, color=Color.PINK)
                ]
            },
            "Winnipeg": {
                "Duluth": [
                    Route(length=4, color=Color.BLACK)
                ],
                "Helena": [
                    Route(length=4, color=Color.BLUE)
                ],
                "Sault St. Marie": [
                    Route(length=6, color=Color.GRAY)
                ],
                "Calgary": [
                    Route(length=6, color=Color.WHITE)
                ]
            },
            "Sault St. Marie": {
                "Duluth": [
                    Route(length=3, color=Color.GRAY)
                ],
                "Winnipeg": [
                    Route(length=6, color=Color.GRAY)
                ],
                "Toronto": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Montreal": [
                    Route(length=5, color=Color.BLACK)
                ]
            },
            "Las Vegas": {
                "Salt Lake City": [
                    Route(length=3, color=Color.ORANGE)
                ],
                "Los Angeles": [
                    Route(length=2, color=Color.GRAY)
                ]
            },
            "Los Angeles": {
                "Las Vegas": [
                    Route(length=2, color=Color.GRAY)
                ],
                "Phoenix": [
                    Route(length=3, color=Color.GRAY)
                ],
                "El Paso": [
                    Route(length=6, color=Color.BLACK)
                ],
                "San Francisco": [
                    Route(length=3, color=Color.PINK),
                    Route(length=3, color=Color.YELLOW)
                ]
            },
            "San Francisco": {
                "Salt Lake City": [
                    Route(length=5, color=Color.ORANGE),
                    Route(length=5, color=Color.WHITE)
                ],
                "Los Angeles": [
                    Route(length=3, color=Color.PINK),
                    Route(length=3, color=Color.YELLOW)
                ],
                "Portland": [
                    Route(length=5, color=Color.GREEN),
                    Route(length=5, color=Color.PINK)
                ]
            },
            "Portland": {
                "San Francisco": [
                    Route(length=5, color=Color.GREEN),
                    Route(length=5, color=Color.PINK)
                ],
                "Seattle": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ],
                "Salt Lake City": [
                    Route(length=6, color=Color.BLUE)
                ]
            },
            "Seattle": {
                "Portland": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ],
                "Helena": [
                    Route(length=6, color=Color.YELLOW)
                ],
                "Calgary": [
                    Route(length=4, color=Color.GRAY)
                ],
                "Vancouver": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ]
            },
            "Vancouver": {
                "Seattle": [
                    Route(length=1, color=Color.GRAY),
                    Route(length=1, color=Color.GRAY)
                ],
                "Calgary": [
                    Route(length=3, color=Color.GRAY)
                ]
            },
            "Calgary": {
                "Vancouver": [
                    Route(length=3, color=Color.GRAY)
                ],
                "Seattle": [
                    Route(length=4, color=Color.GRAY)
                ],
                "Helena": [
                    Route(length=4, color=Color.GRAY)
                ],
                "Winnipeg": [
                    Route(length=6, color=Color.WHITE)
                ]
            }
        }
         # Add these indices at the end:
        self.city_to_routes = {}  # Maps cities to their routes
        self.route_pairs = {}     # Maps (city1,city2) to route objects
        
        # Build indices
        for city1, connections in self.routes.items():
            if city1 not in self.city_to_routes:
                self.city_to_routes[city1] = []
                
            for city2, routes_list in connections.items():
                # Get canonical order of cities (alphabetical)
                key = (city1, city2) if city1 < city2 else (city2, city1)
                
                # Store in route_pairs
                if key not in self.route_pairs:
                    self.route_pairs[key] = []
                self.route_pairs[key].extend(routes_list)
                
                # Store in city_to_routes
                self.city_to_routes[city1].extend([(city2, route) for route in routes_list])

        self.city_names = sorted(list(set(
            [city for routes in self.routes.values() 
                for city in routes.keys()] + 
            [city for city in self.routes.keys()]
        )))
        self.city_to_idx = {city: i for i, city in enumerate(self.city_names)}
        self.idx_to_city = {i: city for i, city in enumerate(self.city_names)}
        
        # Create adjacency matrix for fast lookups
        n = len(self.city_names)
        self.adjacency = [[[] for _ in range(n)] for _ in range(n)]
        
        for city1, connections in self.routes.items():
            i = self.city_to_idx[city1]
            for city2, routes_list in connections.items():
                j = self.city_to_idx[city2]
                self.adjacency[i][j] = routes_list

    def route_lookup(self, city1: str, city2: str) -> List[Route]:
        """AM route lookup for adjacency between two cities"""
        if hasattr(self, 'city_to_idx') and city1 in self.city_to_idx and city2 in self.city_to_idx:
            i = self.city_to_idx[city1]
            j = self.city_to_idx[city2]
            return self.adjacency[i][j]
        return self.get_routes_between_cities(city1, city2)

    def update_player_turn(self):
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        self.current_player = self.players[self.current_player_idx]

    def get_routes_from_city(self, city: str) -> Dict[str, List[Route]]:
        """Get all routes from a city using optimized data structure"""
        if hasattr(self, 'city_to_routes') and city in self.city_to_routes:
            # Group by city2
            result = {}
            for city2, route in self.city_to_routes[city]:
                if city2 not in result:
                    result[city2] = []
                result[city2].append(route)
            return result
        else:
            # Fall back to original implementation
            if city in self.routes:
                return self.routes[city]
            return {}

    def get_routes_between_cities(self, city1: str, city2: str) -> List[Route]:
        """Get routes between cities using optimized lookup"""
        # First, try adjacency matrix for fastest lookup
        if hasattr(self, 'city_to_idx') and city1 in self.city_to_idx and city2 in self.city_to_idx:
            i = self.city_to_idx[city1]
            j = self.city_to_idx[city2]
            if self.adjacency[i][j]:  # If routes exist
                return self.adjacency[i][j]
        
        # Next, try route_pairs
        if hasattr(self, 'route_pairs'):
            key = (city1, city2) if city1 < city2 else (city2, city1)
            if key in self.route_pairs:
                return self.route_pairs[key]
        
        # Fall back to original implementation
        if city1 in self.routes and city2 in self.routes[city1]:
            return self.routes[city1][city2]
        return []
        
    def get_unclaimed_routes(self) -> List[tuple[str, str, Route]]:
        """Get all unclaimed routes using cached results"""
        # Return cached result if available
        if self._unclaimed_routes_cache is not None and self._cache_valid:
            return self._unclaimed_routes_cache
        
        # Otherwise compute and cache
        unclaimed = []
        seen = set()
        
        for city1, routes in self.city_to_routes.items():
            for city2, route in routes:
                # Use canonical ordering to avoid duplicates
                if city1 < city2 and route.claimed_by is None:
                    key = (city1, city2)
                    if key not in seen:
                        unclaimed.append((city1, city2, route))
                        seen.add(key)
        
        # Store in cache
        self._unclaimed_routes_cache = unclaimed
        self._cache_valid = True
        return unclaimed

    def claim_route_helper(self, color: Color, player: str, routes) -> bool:
        """Helper to claim a route and update player state"""
        for route in routes:
            claimed = route.is_claimed()
            if (color == Color.WILD or route.color == color or route.color == Color.GRAY) and not claimed:
                # Update route state
                route.claim(player)
                # Invalidate cache when route is claimed
                self._cache_valid = False    
            else:
                onewayclaim = True
                
        return True
    
    def claim_route(self, city1: str, city2: str, color: Color, player: str) -> bool:
        """Attempt to claim a route between two cities."""
        routes = self.route_lookup(city1, city2)
        if len(routes) == 4:
            direction1 = [routes[0],routes[2]]
            d1 = self.claim_route_helper(color, player, direction1)
            direction2 = [routes[1], routes[3]]
            d2 = self.claim_route_helper(color, player, direction2)
            return d1 or d2
        else: # Only one direction so can claim both
            if self.claim_route_helper(color, player, routes): return True
              
        #print(f"Failed to claim route between {city1} and {city2} with {color}")
        #print (f"Color: {color} is not valid for route between {city1} and {city2}")
        return False

    def get_route_length(self, city1: str, city2: str) -> Optional[int]:
        """Get the length of a specific route."""
        routes = self.route_lookup(city1, city2)
        return routes[0].length
        for route in routes:
            return route.length
        return None
    
    def setup_train_deck(self):
        for color in Color:
            if color != Color.WILD and color != Color.GRAY:
                self.train_deck.extend([color] * 12)
        self.train_deck.extend([Color.WILD] * 14)
        random.shuffle(self.train_deck)

    def draw_train_face(self, i: int, card: Color, player: str):
        """Draw a face-up card."""
        self.face_up_cards.pop(i)
        if self.train_deck.__len__() == 0:
            self.setup_train_deck()
        self.face_up_cards.append(self.train_deck.pop())
        self.players[self.current_player_idx].train_cards[card] += 1
    
    def draw_train_deck(self, player: str):
        """Draw a card from the train deck."""
        if self.train_deck.__len__() == 0:
            self.setup_train_deck()
        card = self.train_deck.pop()
        self.players[self.current_player_idx].train_cards[card] += 1

    def check_all_destinations(self, player) -> List[Tuple[Destination, bool]]:
        # Check if the player has completed all destination tickets using union-find
        destination_results = []
        for destination in player.destinations:
            city1, city2 = destination.city1, destination.city2
            if player.uf.is_connected(city1, city2):
                destination_results.append((destination, True))
            else:
                destination_results.append((destination, False))
        return destination_results
    
    def calc_route_points(self, route_length: int) -> int:
        if route_length == 1:
            return 1
        elif route_length == 2:
            return 2
        elif route_length == 3:
            return 4
        elif route_length == 4:
            return 7
        elif route_length == 5:
            return 10
        elif route_length == 6:
            return 15
        
    def print_owned_routes(self):
        for player in self.players:
            print(f"{player.name} has claimed the following routes:")
            for city1, city2, color in player.claimed_connections:
                print(f"{city1} to {city2} with {color} and length {self.get_route_length(city1, city2)}")

    # MCTS methods
    def copy(self):
        # Create a new instance
        new_state = GameState()
        
        # Copy scalar values
        new_state.current_player_idx = self.current_player_idx
        
        # Create simplified copies of routes (most expensive structure)
        new_state.routes = {}
        for city1, connections in self.routes.items():
            new_state.routes[city1] = {}
            for city2, routes_list in connections.items():
                # Create new Route objects but avoid deep recursion
                new_state.routes[city1][city2] = [Route(r.length, r.color, r.claimed_by) for r in routes_list]
        
        # Copy simple collections directly
        new_state.train_deck = self.train_deck.copy() if self.train_deck else []
        new_state.destination_deck = self.destination_deck.copy() if self.destination_deck else []
        new_state.face_up_cards = self.face_up_cards.copy() if self.face_up_cards else []
        new_state.score = {k: v for k, v in self.score.items()} if self.score else {}
        
        # Copy players more efficiently
        new_state.players = []
        for player in self.players:
            # Create new player with basic attributes
            new_player = Player(name=player.name, remaining_trains=player.remaining_trains)
            
            # Copy collections efficiently
            new_player.train_cards = {color: count for color, count in player.train_cards.items()}
            new_player.destinations = player.destinations.copy() if player.destinations else []
            new_player.claimed_connections = player.claimed_connections.copy() if player.claimed_connections else []
            new_player.claimed_cities = set(player.claimed_cities) if player.claimed_cities else set()
            
            # Copy scalar values
            new_player.points = player.points
            new_player.turn = player.turn
            
            # Recreate UnionFind instead of copying it
            if player.uf:
                new_player.uf = UnionFind(new_state.routes.keys())
                # Only rebuild connections that matter
                for city1, city2, _ in player.claimed_connections:
                    new_player.uf.union(city1, city2)
            
            new_state.players.append(new_player)
        
        # Fix current player reference
        new_state.current_player = new_state.players[new_state.current_player_idx] if new_state.players else None
        
        # Copy indexing structures (these are mostly immutable after creation)
        if hasattr(self, 'city_names'):
            new_state.city_names = self.city_names.copy()
        if hasattr(self, 'city_to_idx'):
            new_state.city_to_idx = self.city_to_idx.copy()
        if hasattr(self, 'idx_to_city'):
            new_state.idx_to_city = self.idx_to_city.copy()
        
        # More efficient copying of lookup structures
        if hasattr(self, 'city_to_routes'):
            new_state.city_to_routes = {}
            for city, routes in self.city_to_routes.items():
                new_state.city_to_routes[city] = routes.copy()
        
        if hasattr(self, 'route_pairs'):
            new_state.route_pairs = {}
            for key, routes in self.route_pairs.items():
                new_state.route_pairs[key] = [Route(r.length, r.color, r.claimed_by) for r in routes]
        
        # Efficiently copy adjacency matrix if it exists
        if hasattr(self, 'adjacency') and self.adjacency:
            n = len(self.adjacency)
            new_state.adjacency = [[[] for _ in range(n)] for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    if self.adjacency[i][j]:  # Only copy non-empty lists
                        new_state.adjacency[i][j] = [Route(r.length, r.color, r.claimed_by) for r in self.adjacency[i][j]]
        
        # Create fresh cache for better performance
        new_state._unclaimed_routes_cache = None
        new_state._cache_valid = False
        
        # Handle FloydWarshall - lazy instantiation
        new_state.fw = self.fw
        
        # Don't copy update reference
        new_state.update = None
        
        return new_state
    
    def apply_action(self, action):
        action_type = action[0]
        if action_type == "draw_two_train_cards":
            idx1, card1, idx2, card2, player_name = action[1:]
            if card1 != "deck":
                self.draw_train_face(idx1, card1, player_name)
            else:
                self.draw_train_deck(player_name)
            if card2 != "deck":
                self.draw_train_face(idx2, card2, player_name)
            else:
                self.draw_train_deck(player_name)
        elif action_type == "claim_route":
            city1, city2, color, player_name = action[1:]
            if self.claim_route(city1, city2, color, player_name):
                route_length = self.get_route_length(city1, city2)
                if color == Color.WILD:
                    self.players[self.current_player_idx].train_cards[Color.WILD] -= route_length
                else:
                    self.players[self.current_player_idx].train_cards[color] -= route_length
                self.players[self.current_player_idx].claimed_connections.append((city1, city2, color))
                self.players[self.current_player_idx].claimed_cities.add(city1)
                self.players[self.current_player_idx].claimed_cities.add(city2)
                self.players[self.current_player_idx].points += self.calc_route_points(route_length)
                self.players[self.current_player_idx].uf.union(city1, city2)
                if route_length >= 5:
                    #print("long route attempted at length", route_length)
                    pass
                self.players[self.current_player_idx].remaining_trains -= route_length
            else:
                pass
        elif action_type == "draw_destination_tickets":
            i, j, k, player_name = action[1:]
            destinations = []
            if i == 1:
                destinations.append(self.destination_deck.pop(0))
            if j == 1:
                destinations.append(self.destination_deck.pop(1))
            if k == 1:
                destinations.append(self.destination_deck.pop(2))
            if i == 0 and j == 0 and k == 0:
                destinations.append(self.destination_deck.pop(random.randint(0, 2)))
            self.current_player.destinations.extend(destinations)

    def apply_action_final(self, action):
        self.apply_action(action)
        action_type = action[0]
        if action_type == "draw_two_train_cards":
            idx1, card1, idx2, card2, player_name = action[1:]
            print(f"{player_name} has drawn two train cards: {card1}, {card2}")
            
        elif action_type == "claim_route":
            city1, city2, color, player_name = action[1:]
            route_length = self.get_route_length(city1, city2)
            print(f"{player_name} has claimed a route of length {route_length} between {city1} and {city2} with {color}")
        if action_type == "draw_destination_tickets":
            i, j, k, player_name = action[1:]
            ijk = sum([i,j,k])
            print(f"{player_name} has drawn destination tickets and kept {ijk}")
            
    
    def is_end(self):
        # Check if the game state is terminal
        for player in self.players:
            if player.remaining_trains <= 2:
                return True
        return False
    
    def get_legal_actions(self):
        legal_actions = []
        current_player = self.players[self.current_player_idx]
        unclaimed_routes = self.get_unclaimed_routes()
        for city1, city2, route in unclaimed_routes:
            if route.color == Color.GRAY:
                for color in Color:
                    if current_player.train_cards[color] >= route.length:
                        legal_actions.append(("claim_route",city1, city2, color, current_player.name))
            if current_player.train_cards[route.color] >= route.length:
                legal_actions.append(("claim_route",city1, city2, route.color, current_player.name))
            if current_player.train_cards[Color.WILD] >= route.length:
                legal_actions.append(("claim_route",city1, city2, Color.WILD, current_player.name))
        
        # TODO - probably should bias towards not drawing from deck too much
        num_cards = sum(current_player.train_cards.values())
        if len(self.train_deck) > 5:
            # Draw two train cards. Enumerate all possible combinations of face-up cards and deck cards
            for i, card1 in enumerate(self.face_up_cards):
                for j, card2 in enumerate(self.face_up_cards):
                    if i != j:
                        legal_actions.append(("draw_two_train_cards", i, card1, j, card2, current_player.name))
                legal_actions.append(("draw_two_train_cards", i, card1, "deck", "deck", current_player.name))
            legal_actions.append(("draw_two_train_cards", "deck", "deck", "deck", "deck", current_player.name))
        # TODO - Definitely should bias towards not drawing destinations if the player hasnt completed many yet
        num_destinations = len(current_player.destinations)
        if num_destinations < 8:
            if len(self.destination_deck) >= 5:
                # Draw destination tickets: scry three, keep minimum one
                for i in range(2):
                    for j in range(2):
                        for k in range(2):
                            legal_actions.append(("draw_destination_tickets", i, j, k, current_player.name))
        
        return legal_actions
    
    def one_off(self,) -> bool:
        #Check if the player only needs one more turn to finish a destination ticket.
        player = self.players[self.current_player_idx]
        for destination in player.destinations:
            city1, city2 = destination.city1, destination.city2
            if player.uf.is_connected(city1,city2):
                continue #destination is already connected, skip
            
            one_off = self.fw.get_one_off_cities(city1)
            if any(player.uf.is_connected(city2, city1off) for city1off in one_off):
                return True
            # other direction
            one_off = self.fw.get_one_off_cities(city2)
            if any(player.uf.is_connected(city1, city2off) for city2off in one_off):
                return True
        return False
    
    def get_longest_route_length(self, player):
        """Calculate the longest continuous route for a player"""
        if not player.claimed_connections:
            return 0
        
        # Build adjacency list from player's claimed connections
        connections = {}
        for city1, city2, _ in player.claimed_connections:
            if city1 not in connections:
                connections[city1] = []
            if city2 not in connections:
                connections[city2] = []
            connections[city1].append(city2)
            connections[city2].append(city1)
        
        # DFS to find longest path from each starting city
        max_length = 0
        
        def dfs(city, visited, path_length):
            visited.add(city)
            longest = path_length
            
            for next_city in connections.get(city, []):
                if next_city not in visited:
                    longest = max(longest, dfs(next_city, visited, path_length + 1))
            
            visited.remove(city)  # Backtrack
            return longest
        
        # Try each city as a starting point
        for city in player.claimed_cities:
            if city in connections:
                length = dfs(city, set(), 0)
                max_length = max(max_length, length)
        
        return max_length
    
    def switch_turn(self):
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        self.current_player = self.players[self.current_player_idx]

    def game_result(self, game_num):
        self.print_score()
        player = self.players[self.current_player_idx]
        opponent = self.players[(self.current_player_idx + 1) % len(self.players)]
        
        # Calculate destination ticket points
        destination_results = self.check_all_destinations(player)
        for destination, is_complete in destination_results:
            if is_complete:
                player.points += destination.points
            else:
                player.points -= destination.points
        
        # Award longest route bonus (10 points)
        player_longest = self.get_longest_route_length(player)
        opponent_longest = self.get_longest_route_length(opponent)
        
        # Store the length for potential display/debugging
        player.longest_route_length = player_longest
        opponent.longest_route_length = opponent_longest
        
        # Award bonus to player with longer route
        if player_longest > opponent_longest:
            player.points += 10  # Bonus for longest route
        elif player_longest < opponent_longest:
            opponent.points += 10
        else:
            player.points += 10  # Award to both players in case of tie
            opponent.points += 10  
        if self.update:
            self.update.publish("mcts_update", game_num, player)
        return player.points
    
    def print_score(self):
        for player in self.players:
            destination_results = self.check_all_destinations(player)
            for destination, is_complete in destination_results:
                if is_complete:
                    player.points += destination.points
                else:
                    player.points -= destination.points
            print(f"Perceived Score {player.name}: {player.points}")
    
    def game_result_final(self, game_num):
        print(f"Game {game_num}:")
        
        # First calculate longest routes
        longest_routes = [(player, self.get_longest_route_length(player)) for player in self.players]
        longest_routes.sort(key=lambda x: x[1], reverse=True)
        
        # Award bonus to player(s) with longest route
        if len(longest_routes) > 1 and longest_routes[0][1] > longest_routes[1][1]:
            longest_player = longest_routes[0][0]
            longest_player.points += 10
            print(f"{longest_player.name} gets 10 bonus points for the longest continuous route of length {longest_routes[0][1]}!")
        
        # Calculate and display final scores for each player
        for player in self.players:
            print(f"Score {player.name}: {player.points}")
            destination_results = self.check_all_destinations(player)
            for destination, is_complete in destination_results:
                if is_complete:
                    player.points += destination.points
                    print(f"Destination between {destination.city1} and {destination.city2} has been completed. Total score: {player.points}")
                else:
                    player.points -= destination.points
                    print(f"Destination between {destination.city1} and {destination.city2} has not been completed. Total score: {player.points}")
            
            # Show longest route length for each player
            print(f"Longest continuous route: {self.get_longest_route_length(player)}")
            print("Final score: ", player.points)
        

# General game class which stores players, current player index, train deck, destination deck, face-up cards
class TicketToRide:
    def __init__(self):
        self.game_state = GameState()
        self.god_mode = False
        
    def setup_game(self, players: List[Player]):
        self.game_state.players = players
        self.game_state.init()
        # Deal initial cards to each player
        for player in self.game_state.players:
            self.deal_initial_cards(player)
        
        self.game_state.init_uf()
    
    def deal_initial_cards(self, player: Player):
        # Deal 4 train cards to each player
        for _ in range(4):
            card = self.game_state.train_deck.pop()
            player.train_cards[card] += 1
        # Deal 3 destination cards, player must keep at least 2
        destinations = [self.game_state.destination_deck.pop() for _ in range(3)]
        # TODO - player must keep at least 2 & can discard 1
        player.destinations.extend(destinations[:3])
                
        print(f"{player.name} has been dealt the following destinations: {', '.join(self.formatted_destinations(player))}")
        print(f"{player.name} has been dealt the following train cards: {', '.join(self.formatted_trains(player))}")

    def formatted_trains(self, player: Player) -> List[str]: 
        return [f"{color.name.capitalize()}: {count}" for color, count in player.train_cards.items() if count > 0]

    def formatted_destinations(self, player: Player) -> List[str]: 
        return [f"{destination.city1} to {destination.city2} ({destination.points})" for destination in player.destinations]

    def print_board(self):
        #self.visualizer = TicketToRideVisualizer(self.game_state)
        #self.visualizer.visualize_game_map()
        print("=== Ticket to Ride Board ===")
        for city1, connections in sorted(self.game_state.routes.items()):
            print(f"\n{city1}:")
            for city2, routes in sorted(connections.items()):
                for route in routes:
                    status = "Claimed by " + route.claimed_by if route.claimed_by else "Available"
                    print(f"  -> {city2} ({route.color} * {route.length}): {status}")
        print("===========================")

    def print_available_routes(self, player: Player):
        unclaimed_routes = self.game_state.get_unclaimed_routes()
        available_routes = []
        
        for city1, city2, route in unclaimed_routes:
            # Check if player has enough cards to claim the route
            if route.color == Color.GRAY:
                for color in Color:
                    if player.train_cards[color] >= route.length:
                        if available_routes.__contains__((city1, city2, route, color)): #if the route is already in the list, skip (avoids duplicates in case of multiple paths /wild cards)
                            continue
                        else:
                            available_routes.append((city1, city2, route, color))
            if player.train_cards[Color.WILD] >= route.length:
                if available_routes.__contains__((city1, city2, route, Color.WILD)):
                    continue
                else:
                    available_routes.append((city1, city2, route, Color.WILD))
            if player.train_cards[route.color] >= route.length:
                if available_routes.__contains__((city1, city2, route, route.color)):
                    continue
                else:
                    available_routes.append((city1, city2, route, route.color))
                
        
        if available_routes:
            print("\nRoutes you can complete:")
            for city1, city2, route, color in available_routes:
                print(f"{city1} -> {city2} ({color} * {route.length})")
        else:
            print("\nNo routes available to claim with your current cards.")

    def destination_completion_check(self, player: Player):
        results = self.game_state.check_all_destinations(player)
        
        completed_count = 0
        for destination, is_completed in results:
            status = "completed" if is_completed else "not completed"
            print(f"Destination {destination.city1} to {destination.city2} is {status}")
            if is_completed:
                completed_count += 1
                
        print(f"\nTotal completed destinations: {completed_count}/{len(results)}")
        
    def play_turn(self, player: Player):
        print("\n" + "_" * 200)
        print(f"Turn {player.turn}" + "\n")
        print(f"\n{player.name}'s turn")
        print(f"{player.name}'s train cards: {', '.join(self.formatted_trains(player))}")
        print(f"{player.name}'s destination tickets: {', '.join(self.formatted_destinations(player))}")
        print(f"Face-up cards: {', '.join([card.name for card in self.game_state.face_up_cards])}" + "\n")

        choice = input("<1: Draw Train cards, 2: Claim a route, 3: Draw destination tickets, 4: Print board, 5: Print routes you can complete, 6: Print score, exit: Exit game>\n")

        if choice == "1":
            self.draw_train_cards(player)
        elif choice == "2":
            self.handle_claim_route(player)
            if self.god_mode:
                self.play_turn(player)
        elif choice == "3":
            self.draw_destination_tickets(player)
        elif choice == "4":
            self.print_board()
            self.play_turn(player)
        elif choice == "5":
            self.print_available_routes(player)
            self.play_turn(player)
        elif choice == "6":
            print(f"{player.name}'s score: {player.points}")
            self.play_turn(player)
        elif choice == "7": #temporary testing
            self.destination_completion_check(player)
            self.play_turn(player)
        elif choice == "godmode":
            # testing cheats
            self.god_mode = True
            self.game_state.players[0].train_cards[Color.WILD] += 100
            self.game_state.players[1].train_cards[Color.WILD] += 100
            self.play_turn(player)
        elif choice == "exit":
            exit()
        else:
            print("Invalid choice, please try again.")
            self.play_turn(player)
        

    def handle_claim_route(self, player: Player):
        print("Choose a route to claim:")
        city1 = input("Enter the first city: ")
        if city1 == "back":
            self.play_turn(player)
            return
            
        city2 = input("Enter the second city: ")
        if city2 == "back":
            self.play_turn(player)
            return

        routes = self.game_state.get_routes_between_cities(city1, city2)
        if not routes:
            print("No route exists between these cities.")
            self.play_turn(player)
            return

        available_colors = []
        
        route = routes[0]
        if route.claimed_by is None:
            # TODO allow player to use a combination of wild and other colors
            if route.color == Color.GRAY:
                for color in Color:
                    if player.train_cards[color] >= route.length:
                        available_colors.append(color)
            if player.train_cards[route.color] >= route.length:
                available_colors.append(route.color)
            

            if player.train_cards[Color.WILD] >= route.length:
                available_colors.append(Color.WILD)

        if available_colors == []:
            print("You don't have enough cards to claim any routes between these cities.")
            self.play_turn(player)
            return 
        
        if len(available_colors) > 1:
            color = input(f"Choose a color to claim the route ({', '.join([colors.name for colors in available_colors])}): ")
            if color == "back":
                self.play_turn(player)
                return
            for colors in available_colors:
                if color == colors.name:
                    color = colors
            if color not in available_colors:
                print("Invalid color choice, please try again.")
                # TODO probably make a color choice function
                self.handle_claim_route(player)
                return
        else:
            color = available_colors[0]
        if self.game_state.claim_route(city1, city2, color, player.name):
            # Remove cards from player's hand
            route_length = self.game_state.get_route_length(city1, city2)
            if color == Color.WILD:
                player.train_cards[Color.WILD] -= route_length
            else:
                player.train_cards[color] -= route_length
            player.claimed_connections.append((city1, city2, color))
            player.claimed_cities.add(city1)
            player.claimed_cities.add(city2)
            player.points += self.game_state.calc_route_points(route_length)
            print(f"{player.name} has claimed the route between {city1} and {city2} with {color}")
            player.uf.union(city1, city2)
        else:
            print("Failed to claim route.")
            self.play_turn(player)

    def draw_train_cards(self, player: Player):
        drawn = 0
        while drawn < 2:
            # TODO only allow play to pick up 1 card if they take a wild card, disallow from taking a wild as second card
            choice = input("Would you like to draw from the face-up cards? (y/n)")
            if choice == "y":
                print("Choose a card to draw:")
                for i, card in enumerate(self.game_state.face_up_cards):
                    print(f"{i+1}: {card.name}")
                card_choice = int(input("Enter the card number: ")) - 1
                card = self.game_state.face_up_cards.pop(card_choice)
                player.train_cards[card] += 1
                print(f"{player.name} has drawn {card.name}")
                self.game_state.face_up_cards.append(self.game_state.train_deck.pop())
                print(f"New face-up cards: {', '.join([card.name for card in self.game_state.face_up_cards])}")
                drawn += 1
            elif choice == "n":
                card = self.game_state.train_deck.pop()
                player.train_cards[card] += 1
                print(f"{player.name} has drawn {card.name}")
                drawn += 1
            elif choice == "back":
                self.play_turn(player)
                return
            else:
                print("Invalid choice, please try again.")

        print(f"{player.name}'s train cards: {', '.join(self.formatted_trains(player))}")

    def draw_destination_tickets(self, player: Player):
        destinations = [self.game_state.destination_deck.pop() for _ in range(3)]
        print("You have drawn the following destinations:")
        for i, dest in enumerate(destinations, 1):
            print(f"{i}: {dest.city1} to {dest.city2} ({dest.points} points)")
        
        to_keep = destinations.copy()
        while len(to_keep) > 1:  # Must keep at least one
            choice = input("Would you like to remove any destinations? (y/n)")
            if choice == "y":
                print("Which destination would you like to remove?")
                for i, dest in enumerate(to_keep, 1):
                    print(f"{i}: {dest.city1} to {dest.city2} ({dest.points} points)")
                try:
                    remove_idx = int(input("Enter the destination number to remove: ")) - 1
                    removed = to_keep.pop(remove_idx)
                    print(f"Removed: {removed.city1} to {removed.city2}")
                except (ValueError, IndexError):
                    print("Invalid choice, please try again.")
            elif choice == "n":
                break
            elif choice == "back":
                self.play_turn(player)
                return

        player.destinations.extend(to_keep)
        print(f"{player.name}'s current destinations: {', '.join(self.formatted_destinations(player))}")

def main():
    timestart=time.time()
    game = TicketToRide()
    # Create players
    players = [
        Player(name="Player 1", train_cards={color: 0 for color in Color}, 
            destinations=[], claimed_connections=[], points=0, turn=1),
        Player(name="Player 2", train_cards={color: 0 for color in Color}, 
            destinations=[], claimed_connections=[], points=0, turn=1)
    ]

    print("\n" + "_" * 200 + "\n")
    # Set up and start the game
    game.setup_game(players)

    print("You can type back to go to the previous menu option")
    print("Enjoy Ticket to Ride!")

    console = LiveConsole()
    num_sims = 1000
    console.total_expected_games = num_sims

    # Main game loop
    game_end = False
    while not game_end:
        current_player = game.game_state.players[game.game_state.current_player_idx]
        
        if current_player.name == "Player 1":
            print(f"\nTurn: {current_player.turn}")
            tst = time.time()
            #console.start_live()
            # Use MCTS to determine the best action for Player 1
            mcts_player = MCTS(game.game_state)
            #best_action = mcts_player.best_action_multi(console.update_display, num_sims)
            best_action = mcts_player.best_action(num_sims) # single processed
            game.game_state.apply_action_final(best_action)
            current_player.turn += 1
            tet = time.time()
            print(f"Time taken for turn: {tet-tst} seconds")
            #console.stop()
        # Player 2 Random Moves
        elif current_player.name == "Player 2":
            random = RandomAgent(game.game_state)
            move = random.get_action()
            game.game_state.apply_action_final(move)
            current_player.turn += 1
            #console.stop()

        """ Player 2 MCTS
        elif current_player.name == "Player 2":
            mcts_player2 = MCTS(game.game_state)
            best_action = mcts_player2.best_action_multi(simulations_number=2000)
            game.game_state.apply_action_final(best_action)
            #console.stop()
        """
        """ Player 2 Manual
        else:
            # Let Player 2 play their turn manually
            game.play_turn(current_player)
        """
        
        game.game_state.update_player_turn()
        
        # Check end game condition
        if current_player.remaining_trains <= 2:
            game_end = True
    
    # Calculate final scores
    game.game_state.game_result_final(1)

    #game.game_state.visualizer = TicketToRideVisualizer(game.game_state)
    #game.game_state.visualizer.visualize_game_map() #visualize the final state of the game board

    timeend=time.time()
    elapsed_time = timeend - timestart
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)

    print(f"Time taken: {minutes} minutes and {seconds} seconds")

    game.game_state.print_owned_routes()

if __name__ == "__main__":
    main()
    