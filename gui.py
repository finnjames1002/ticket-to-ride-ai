import queue
import threading

import pygame

from helper_classes import Colour


class TicketToRideGUI:
    # City coordinates for USA map
    USA_CITY_POSITIONS = {
        "Seattle": (90, 100),
        "Portland": (120, 150),
        "San Francisco": (100, 300),
        "Los Angeles": (130, 410),
        "Salt Lake City": (250, 250),
        "Las Vegas": (190, 330),
        "Phoenix": (230, 370),
        "Denver": (300, 280),
        "Santa Fe": (300, 350),
        "Oklahoma City": (400, 350),
        "Dallas": (420, 400),
        "Houston": (440, 440),
        "El Paso": (310, 420),
        "Winnipeg": (400, 100),
        "Duluth": (450, 200),
        "Omaha": (400, 250),
        "Kansas City": (400, 300),
        "Chicago": (500, 250),
        "Saint Louis": (470, 310),
        "Nashville": (520, 360),
        "New Orleans": (500, 450),
        "Little Rock": (450, 370),
        "Toronto": (600, 200),
        "Pittsburgh": (580, 260),
        "Washington": (620, 300),
        "Raleigh": (600, 340),
        "Atlanta": (550, 380),
        "Charleston": (600, 380),
        "Miami": (620, 480),
        "New York": (640, 240),
        "Boston": (680, 210),
        "Montreal": (650, 140),
        "Sault St. Marie": (520, 160),
        "Calgary": (200, 100),
        "Helena": (250, 180),
        "Vancouver": (100, 80),
    }

    # City coordinates for Europe map
    EUROPE_CITY_POSITIONS = {
        "Edinburgh": (180, 150),
        "London": (200, 220),
        "Amsterdam": (280, 220),
        "Bruxelles": (270, 250),
        "Paris": (250, 300),
        "Dieppe": (220, 270),
        "Brest": (150, 300),
        "Pamplona": (200, 400),
        "Madrid": (150, 450),
        "Lisboa": (80, 470),
        "Cadiz": (130, 520),
        "Barcelona": (250, 430),
        "Marseille": (300, 380),
        "Zurich": (320, 320),
        "Frankfurt": (330, 270),
        "Munchen": (370, 300),
        "Venezia": (370, 350),
        "Roma": (370, 410),
        "Brindisi": (420, 440),
        "Palermo": (380, 480),
        "Kobenhavn": (350, 180),
        "Essen": (330, 230),
        "Berlin": (380, 230),
        "Danzic": (430, 200),
        "Stockholm": (400, 130),
        "Riga": (470, 170),
        "Petrograd": (530, 150),
        "Warszawa": (450, 250),
        "Wien": (410, 300),
        "Budapest": (450, 330),
        "Kyiv": (530, 310),
        "Wilno": (500, 230),
        "Smolensk": (550, 230),
        "Moskva": (600, 200),
        "Kharkov": (580, 320),
        "Rostov": (630, 350),
        "Bucuresti": (500, 370),
        "Sofia": (480, 400),
        "Constantinople": (520, 430),
        "Angora": (580, 450),
        "Sevastopol": (570, 390),
        "Erzurum": (650, 430),
        "Athina": (470, 460),
        "Smyrna": (520, 470),
        "Sarajevo": (460, 380),
        "Zagrab": (420, 350),
        "Sochi": (630, 370),
    }

    def __init__(self):
        # initialise pygame
        pygame.init()

        # Constants
        self.WIDTH = 1200
        self.HEIGHT = 800
        self.BACKGROUND_colour = (240, 230, 200)
        self.TEXT_colour = (0, 0, 0)
        self.HIGHLIGHT_colour = (255, 255, 0)
        self.PLAYER_colours = [(255, 0, 0), (0, 0, 255), (0, 128, 0), (255, 165, 0)]
        self.CITY_colour = (100, 100, 100)
        self.ROUTE_colour = (150, 150, 150)
        self.FONT_SIZE = 20

        # State variables
        self.city_positions = {}
        self.screen = None
        self.font = None
        self.action_log = []
        self.running = False

        # Thread management
        self.update_queue = queue.Queue()
        self.command_queue = queue.Queue()
        self.gui_thread = None

    def initialise(self):
        """initialise the GUI in a separate thread"""
        # Don't start a new thread if one is already running
        if self.gui_thread and self.gui_thread.is_alive():
            return True

        # Initially set city_positions to empty (will be populated later)
        self.city_positions = {}

        try:
            # Create and start the GUI thread
            self.gui_thread = self._GUIThread(self)
            self.gui_thread.start()

            # Wait for the thread to be ready
            if not self.gui_thread.ready.wait(timeout=5.0):
                print("GUI thread initialisation timed out")
                return False

            return True
        except Exception as e:
            print(f"Failed to initialise GUI: {e}")
            return False

    def update_game_state(self, game, action=None):
        """Update the GUI with the current game state"""
        if not self.running or not self.gui_thread or not self.gui_thread.is_alive():
            return

        try:
            # Determine which map type is being used (only needs to be done once)
            if not self.city_positions:
                self.set_map_type(game)

            # Calculate current turn based on players' turn numbers
            current_turn = max(player.turn for player in game.players)

            # Create a thread-safe copy of the game state
            game_state = {
                "players": [],
                "current_player_idx": game.current_player_idx,
                "connections": [],
                "turn": current_turn,
                "route_info": {},
            }

            # Add action if provided
            if action:
                game_state["action"] = self.format_action(action)

            # Get connections and route information
            if hasattr(game, "routes") and game.routes:
                for city1, destinations in game.routes.items():
                    for city2 in destinations:
                        if city1 < city2:  # Only add each connection once
                            game_state["connections"].append((city1, city2))

                            # Add route information
                            route_key = f"{city1}-{city2}"
                            routes = game.route_lookup(city1, city2)
                            route_infos = []

                            for route in routes:
                                route_infos.append(
                                    {
                                        "colour": route.colour,
                                        "length": route.length,
                                        "claimed_by": route.claimed_by,
                                    }
                                )

                            game_state["route_info"][route_key] = route_infos

            # Convert players to dict
            for i, player in enumerate(game.players):
                # Get agent type
                agent_type = ""
                if hasattr(game, "player_agents") and player.name in game.player_agents:
                    agent_id = game.player_agents[player.name]
                    if (
                        hasattr(game, "agent_options")
                        and agent_id in game.agent_options
                    ):
                        agent_type = game.agent_options[agent_id]
                    else:
                        agent_types = {
                            1: "Human Player",
                            2: "MCTS Tuned AI",
                            3: "MCTS Rollouts AI",
                            4: "MCTS Selection AI",
                            5: "MCTS Untuned AI",
                            6: "Destination Heuristic AI",
                            7: "Longest Route Heuristic AI",
                            8: "Best Move Heuristic AI",
                            9: "Random AI",
                        }
                        agent_type = agent_types.get(agent_id, f"Agent {agent_id}")

                player_dict = {
                    "name": player.name,
                    "agent_type": agent_type,
                    "points": player.points,
                    "remaining_trains": player.remaining_trains,
                    "train_cards": dict(player.train_cards),
                    "destinations": list(player.destinations),
                    "claimed_connections": [
                        list(conn) for conn in player.claimed_connections
                    ],
                }
                game_state["players"].append(player_dict)

            # Send to GUI thread through queue
            self.update_queue.put(game_state)
        except Exception as e:
            print(f"Error updating game state: {e}")

    def shutdown(self):
        """Safely shutdown the GUI thread"""
        if self.running and self.gui_thread and self.gui_thread.is_alive():
            print("Sending shutdown command to GUI thread...")
            self.command_queue.put("quit")

            self.gui_thread.join(timeout=2.0)

            if self.gui_thread.is_alive():
                print("GUI thread did not terminate gracefully")
            else:
                print("GUI thread terminated successfully")

        self.running = False

    def set_map_type(self, game):
        """Determine which map is being used and set the appropriate city positions"""
        # Check if this is a Europe map by looking for European cities
        europe_cities = ["London", "Paris", "Berlin", "Roma"]
        usa_cities = ["Seattle", "New York", "Chicago", "Los Angeles"]

        # Check which cities are in the game's city_to_idx dictionary
        if hasattr(game, "city_to_idx"):
            # Check if European cities are present
            europe_count = sum(1 for city in europe_cities if city in game.city_to_idx)
            usa_count = sum(1 for city in usa_cities if city in game.city_to_idx)

            if europe_count > usa_count:
                self.city_positions = self.EUROPE_CITY_POSITIONS
                print("Detected Europe map")
                return "Europe"
            else:
                self.city_positions = self.USA_CITY_POSITIONS
                print("Detected USA map")
                return "USA"

        # If we can't determine, default to USA map
        self.city_positions = self.USA_CITY_POSITIONS
        print("Defaulting to USA map")
        return "USA"

    def format_action(self, action):
        """Format an action for display"""
        if not action:
            return "No action"
        try:
            action_type = action[0]
            player_name = action[-1]  # Player name is the last element

            if action_type == "claim_route":
                return f"{player_name} claimed route: {action[1]} to {action[2]} with {action[3].value} cards"
            elif action_type == "draw_two_train_cards":
                card1 = "deck" if action[2] == "deck" else action[2]
                card2 = "deck" if action[4] == "deck" else action[4]

                if card1 == Colour.WILD:
                    return f"{player_name} drew 1 {card1.value}"
                if card1 == "deck" and card2 == "deck":
                    return f"{player_name} drew 2 cards from deck"
                elif card1 == "deck":
                    return (
                        f"{player_name} drew 1 card from deck and 1 {card2.value} card"
                    )
                elif card2 == "deck":
                    return (
                        f"{player_name} drew 1 {card1.value} card and 1 card from deck"
                    )
                elif card1 == card2:
                    return f"{player_name} drew 2 {card1.value} cards"
                else:
                    return f"{player_name} drew 1 {card1.value} card and 1 {card2.value} card"
            elif action_type == "draw_destination_tickets":
                kept_count = action[1] + action[2] + action[3]
                return f"{player_name} drew destination tickets and kept {kept_count}"
            else:
                return f"{player_name}: {str(action)}"
        except Exception as e:
            print(f"Error formatting action: {e}")
            return str(action)

    class _GUIThread(threading.Thread):
        """Internal thread class that handles the pygame display loop"""

        def __init__(self, parent):
            threading.Thread.__init__(self, daemon=True)
            self.parent = parent
            self.game_state = None
            self.ready = threading.Event()

        def run(self):
            try:
                # initialise pygame display
                print("initialising GUI thread...")
                self.parent.screen = pygame.display.set_mode(
                    (self.parent.WIDTH, self.parent.HEIGHT)
                )
                pygame.display.set_caption("Ticket to Ride AI - Game Viewer")
                self.parent.font = pygame.font.SysFont("Arial", self.parent.FONT_SIZE)

                self.parent.running = True
                self.ready.set()
                print("GUI thread ready")

                # Initial screen setup
                self.parent.screen.fill(self.parent.BACKGROUND_colour)
                self._draw_initial_screen()
                pygame.display.flip()

                # Main GUI loop
                clock = pygame.time.Clock()
                while self.parent.running:
                    # Process pygame events
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            self._handle_quit()

                    # Check for commands from main thread
                    try:
                        while not self.parent.command_queue.empty():
                            cmd = self.parent.command_queue.get_nowait()
                            if cmd == "quit":
                                self._handle_quit()
                                break
                    except queue.Empty:
                        pass

                    # Check for game state updates
                    try:
                        while not self.parent.update_queue.empty():
                            self.game_state = self.parent.update_queue.get_nowait()
                            self._update_display()
                    except queue.Empty:
                        pass

                    clock.tick(30)

                print("GUI thread exiting normally")
            except Exception as e:
                print(f"Error in GUI thread: {e}")
            finally:
                # Clean up
                self.parent.running = False
                pygame.quit()

        def _handle_quit(self):
            self.parent.running = False
            print("GUI shutdown requested")

        def _draw_initial_screen(self):
            """Draw the initial screen before any game state is available"""
            self.parent.screen.fill(self.parent.BACKGROUND_colour)
            font = pygame.font.SysFont("Arial", 24)
            text = font.render(
                "Waiting for game to start...", True, self.parent.TEXT_colour
            )
            text_rect = text.get_rect(
                center=(self.parent.WIDTH // 2, self.parent.HEIGHT // 2)
            )
            self.parent.screen.blit(text, text_rect)

        def _update_display(self):
            """Update the display with current game state"""
            if not self.game_state:
                return

            try:
                # Clear screen
                self.parent.screen.fill(self.parent.BACKGROUND_colour)

                # Draw game elements
                self._draw_map()
                self._draw_player_routes()
                self._draw_cities()
                self._draw_player_info()
                self._draw_action()

                # Update display
                pygame.display.flip()
            except Exception as e:
                print(f"Error updating display: {e}")

        def _draw_map(self):
            """Draw the game map with cities and routes, showing route lengths with dashed lines"""
            try:
                # Draw background
                pygame.draw.rect(
                    self.parent.screen, (220, 200, 160), (50, 50, 700, 500)
                )

                # Define colours for routes
                colour_map = {
                    Colour.RED: (200, 50, 50),
                    Colour.BLUE: (50, 50, 200),
                    Colour.GREEN: (50, 150, 50),
                    Colour.YELLOW: (200, 200, 50),
                    Colour.BLACK: (50, 50, 50),
                    Colour.WHITE: (230, 230, 230),
                    Colour.ORANGE: (230, 130, 50),
                    Colour.PINK: (230, 130, 200),
                    Colour.GRAY: (130, 130, 130),
                }

                # Create a dictionary to store claimed routes with their specific indices
                claimed_routes_with_idx = {}
                if self.game_state and "players" in self.game_state:
                    for player in self.game_state["players"]:
                        if "claimed_connections" in player:
                            for conn in player["claimed_connections"]:
                                if len(conn) >= 2:
                                    city1, city2 = conn[0], conn[1]
                                    key = tuple(sorted([city1, city2]))

                                    # Initialise the list for this city pair if needed
                                    if key not in claimed_routes_with_idx:
                                        claimed_routes_with_idx[key] = []

                                    # Store player and route information
                                    claimed_routes_with_idx[key].append(conn)

                if self.game_state and "connections" in self.game_state:
                    for city1, city2 in self.game_state["connections"]:
                        key = tuple(sorted([city1, city2]))

                        # Skip if we don't have positions for both cities
                        if (
                            city1 not in self.parent.city_positions
                            or city2 not in self.parent.city_positions
                        ):
                            continue

                        pos1 = self.parent.city_positions[city1]
                        pos2 = self.parent.city_positions[city2]

                        # Get route information for this connection
                        route_infos = []

                        if "route_info" in self.game_state:
                            route_key = (
                                f"{city1}-{city2}"
                                if city1 < city2
                                else f"{city2}-{city1}"
                            )
                            if route_key in self.game_state["route_info"]:
                                route_infos = self.game_state["route_info"][route_key]

                        # Check if we have route information
                        if not route_infos:
                            # Fallback to default
                            route_colour = Colour.GRAY
                            route_length = 1
                            pygame_colour = colour_map.get(
                                route_colour, (130, 130, 130)
                            )

                            # Draw dashed line with default values
                            self._draw_dashed_line(
                                pos1, pos2, pygame_colour, route_length
                            )
                        else:
                            # For routes with multiple tracks, we need to handle offsets properly
                            for i, route_info in enumerate(route_infos):
                                route_colour = route_info.get("colour", Colour.GRAY)
                                route_length = route_info.get("length", 1)
                                claimed_by = route_info.get("claimed_by", None)

                                # Skip if claimed - will be drawn in _draw_player_routes
                                if claimed_by is not None:
                                    continue

                                pygame_colour = colour_map.get(
                                    route_colour, (130, 130, 130)
                                )

                                # Calculate offset for parallel routes
                                if len(route_infos) > 1:
                                    # Calculate perpendicular vector for offset
                                    dx = pos2[0] - pos1[0]
                                    dy = pos2[1] - pos1[1]
                                    length = max(
                                        1, (dx**2 + dy**2) ** 0.5
                                    )  # Avoid division by zero

                                    nx = -dy / length
                                    ny = dx / length

                                    # Apply offset based on route index and claimed status
                                    # This ensures unclaimed routes stay in proper position
                                    offset = 5 if i == 0 else -5
                                    pos1_offset = (
                                        int(pos1[0] + nx * offset),
                                        int(pos1[1] + ny * offset),
                                    )
                                    pos2_offset = (
                                        int(pos2[0] + nx * offset),
                                        int(pos2[1] + ny * offset),
                                    )
                                else:
                                    pos1_offset = pos1
                                    pos2_offset = pos2

                                # Draw dashed line with proper colour and length
                                self._draw_dashed_line(
                                    pos1_offset,
                                    pos2_offset,
                                    pygame_colour,
                                    route_length,
                                )

                # Draw all cities as dots
                for city, pos in self.parent.city_positions.items():
                    pygame.draw.circle(
                        self.parent.screen, self.parent.CITY_colour, pos, 5
                    )
            except Exception as e:
                print(f"Error drawing map: {e}")

        def _draw_dashed_line(self, start_pos, end_pos, colour, num_segments):
            """Draw a dashed line with consistent dash sizes regardless of distance"""
            # Calculate the direction vector
            dx = end_pos[0] - start_pos[0]
            dy = end_pos[1] - start_pos[1]

            # Calculate total distance
            distance = max(1, (dx**2 + dy**2) ** 0.5)

            # normalise
            if distance > 0:
                dx /= distance
                dy /= distance

            FIXED_DASH_LENGTH = 6
            FIXED_SPACE_LENGTH = 4

            segment_length = FIXED_DASH_LENGTH + FIXED_SPACE_LENGTH
            max_possible_segments = int(distance / segment_length)

            # Use the minimum of the requested segments or what can fit
            actual_segments = max(1, min(num_segments, max_possible_segments))

            # Calculate spacing
            total_length = (
                actual_segments * FIXED_DASH_LENGTH
                + (actual_segments - 1) * FIXED_SPACE_LENGTH
            )
            scaling_factor = distance / total_length if total_length > 0 else 1

            # Apply scaling
            dash_length = FIXED_DASH_LENGTH * scaling_factor
            space_length = FIXED_SPACE_LENGTH * scaling_factor

            # Start position
            x, y = start_pos

            # Draw all segments except the last one
            for i in range(actual_segments - 1):
                dash_start = (int(x), int(y))

                x += dx * dash_length
                y += dy * dash_length
                dash_end = (int(x), int(y))

                # Draw the dash
                pygame.draw.line(self.parent.screen, colour, dash_start, dash_end, 2)

                # Move to start of next dash (skip the space)
                x += dx * space_length
                y += dy * space_length

            if actual_segments > 0:
                # Start of last dash
                dash_start = (int(x), int(y))

                # Make sure the last dash ends exactly at end_pos
                pygame.draw.line(self.parent.screen, colour, dash_start, end_pos, 2)

        def _draw_cities(self):
            """Draw city names on the map"""
            try:
                # Draw all city names (with smaller font to avoid clutter)
                small_font = pygame.font.SysFont("Arial", 12)

                for city, pos in self.parent.city_positions.items():
                    text = small_font.render(city, True, self.parent.TEXT_colour)
                    self.parent.screen.blit(text, (pos[0] - 15, pos[1] - 15))
            except Exception as e:
                print(f"Error drawing cities: {e}")

        def _draw_player_routes(self):
            """Draw claimed routes on the map with player colours on top of route colours"""
            try:
                if not self.game_state or "players" not in self.game_state:
                    return

                # Track which routes have been claimed to handle double routes
                claimed_routes = {}

                # Define colours
                colour_map = {
                    Colour.RED: (200, 50, 50),
                    Colour.BLUE: (50, 50, 200),
                    Colour.GREEN: (50, 150, 50),
                    Colour.YELLOW: (200, 200, 50),
                    Colour.BLACK: (50, 50, 50),
                    Colour.WHITE: (230, 230, 230),
                    Colour.ORANGE: (230, 130, 50),
                    Colour.PINK: (230, 130, 200),
                    Colour.GRAY: (130, 130, 130),
                }

                # collect all claimed routes by all players
                for i, player in enumerate(self.game_state["players"]):
                    if "claimed_connections" in player:
                        for connection in player["claimed_connections"]:
                            if len(connection) >= 3:
                                city1, city2, route_colour = (
                                    connection[0],
                                    connection[1],
                                    connection[2],
                                )
                                route_key = tuple(sorted([city1, city2]))

                                if route_key not in claimed_routes:
                                    claimed_routes[route_key] = []
                                claimed_routes[route_key].append((i, route_colour))

                # draw all routes with appropriate offsets
                for route_key, claims in claimed_routes.items():
                    city1, city2 = route_key

                    if (
                        city1 in self.parent.city_positions
                        and city2 in self.parent.city_positions
                    ):
                        pos1 = self.parent.city_positions[city1]
                        pos2 = self.parent.city_positions[city2]

                        # Calculate vectors
                        dx = pos2[0] - pos1[0]
                        dy = pos2[1] - pos1[1]
                        length = max(1, (dx**2 + dy**2) ** 0.5)

                        nx = -dy / length
                        ny = dx / length

                        route_length = None
                        try:
                            # Look up route length from route_info
                            route_key_str = (
                                f"{city1}-{city2}"
                                if city1 < city2
                                else f"{city2}-{city1}"
                            )
                            if (
                                "route_info" in self.game_state
                                and route_key_str in self.game_state["route_info"]
                            ):
                                route_infos = self.game_state["route_info"][
                                    route_key_str
                                ]
                                if route_infos and "length" in route_infos[0]:
                                    route_length = route_infos[0]["length"]
                        except:
                            route_length = 1

                        if not route_length or route_length < 1:
                            route_length = 1

                        # Draw each player's claim
                        for idx, (player_idx, route_colour) in enumerate(claims):
                            player_colour = self.parent.PLAYER_colours[
                                player_idx % len(self.parent.PLAYER_colours)
                            ]

                            if isinstance(route_colour, str):
                                try:
                                    route_colour = Colour[route_colour.upper()]
                                except:
                                    route_colour = Colour.GRAY
                            original_colour = colour_map.get(
                                route_colour, (130, 130, 130)
                            )

                            # Calculate offset based on number of claims
                            if len(claims) == 1:
                                offset = 0  # No offset for single claim
                            else:
                                offset = 5 if idx == 0 else -5

                            pos1_offset = (
                                int(pos1[0] + nx * offset),
                                int(pos1[1] + ny * offset),
                            )
                            pos2_offset = (
                                int(pos2[0] + nx * offset),
                                int(pos2[1] + ny * offset),
                            )

                            # draw dashed line with route colour
                            self._draw_dashed_line(
                                pos1_offset, pos2_offset, original_colour, route_length
                            )

                            # draw player colour on top
                            pygame.draw.line(
                                self.parent.screen,
                                player_colour,
                                pos1_offset,
                                pos2_offset,
                                2,
                            )

                            # circles at endpoints
                            pygame.draw.circle(
                                self.parent.screen, player_colour, pos1_offset, 4
                            )
                            pygame.draw.circle(
                                self.parent.screen, player_colour, pos2_offset, 4
                            )

                            # circle in middle
                            mid_x = (pos1_offset[0] + pos2_offset[0]) // 2
                            mid_y = (pos1_offset[1] + pos2_offset[1]) // 2
                            pygame.draw.circle(
                                self.parent.screen, player_colour, (mid_x, mid_y), 3
                            )

            except Exception as e:
                print(f"Error drawing player routes: {e}")

        def _draw_player_info(self):
            """Draw player information panels"""
            try:
                if not self.game_state or "players" not in self.game_state:
                    return

                panel_width = 350
                panel_height = 120
                panel_x = 800

                for i, player in enumerate(self.game_state["players"]):
                    panel_y = 50 + i * (panel_height + 10)

                    if i == self.game_state.get("current_player_idx", 0):
                        pygame.draw.rect(
                            self.parent.screen,
                            self.parent.HIGHLIGHT_colour,
                            (
                                panel_x - 5,
                                panel_y - 5,
                                panel_width + 10,
                                panel_height + 10,
                            ),
                        )
                    # draw panel bg
                    pygame.draw.rect(
                        self.parent.screen,
                        (255, 255, 255),
                        (panel_x, panel_y, panel_width, panel_height),
                    )

                    player_name = f"Player {i + 1}"
                    agent_type = player.get("agent_type", "")

                    if agent_type:
                        name_text = self.parent.font.render(
                            f"{player_name}: {agent_type}",
                            True,
                            self.parent.TEXT_colour,
                        )
                    else:
                        name_text = self.parent.font.render(
                            f"{player_name}", True, self.parent.TEXT_colour
                        )

                    self.parent.screen.blit(name_text, (panel_x + 10, panel_y + 10))

                    # Draw player stats
                    self._draw_player_stats(player, panel_x, panel_y)
            except Exception as e:
                print(f"Error drawing player info: {e}")

        def _draw_player_stats(self, player, panel_x, panel_y):
            """Draw player statistics in the panel"""
            # Score
            score_text = self.parent.font.render(
                f"Score: {player.get('points', 0)}", True, self.parent.TEXT_colour
            )
            self.parent.screen.blit(score_text, (panel_x + 10, panel_y + 40))

            # Trains remaining
            trains_text = self.parent.font.render(
                f"Trains: {player.get('remaining_trains', 45)}",
                True,
                self.parent.TEXT_colour,
            )
            self.parent.screen.blit(trains_text, (panel_x + 10, panel_y + 70))

            # Cards
            cards_text = self.parent.font.render(
                f"Cards: {sum(player.get('train_cards', {}).values())}",
                True,
                self.parent.TEXT_colour,
            )
            self.parent.screen.blit(cards_text, (panel_x + 150, panel_y + 40))

            # Destination tickets
            dest_text = self.parent.font.render(
                f"Destinations: {len(player.get('destinations', []))}",
                True,
                self.parent.TEXT_colour,
            )
            self.parent.screen.blit(dest_text, (panel_x + 150, panel_y + 70))

        def _draw_action(self):
            """Draw the most recent action and turn counter"""
            try:
                # Action panel
                panel_x = 50
                panel_y = 580
                panel_width = 700
                panel_height = 170

                pygame.draw.rect(
                    self.parent.screen,
                    (255, 255, 255),
                    (panel_x, panel_y, panel_width, panel_height),
                )

                # Draw turn counter
                turn = self.game_state.get("turn", 1)
                title_text = self.parent.font.render(
                    f"Turn {turn} - Recent Actions:", True, self.parent.TEXT_colour
                )
                self.parent.screen.blit(title_text, (panel_x + 10, panel_y + 10))

                # display action log
                if "action" in self.game_state:
                    self.parent.action_log.append(self.game_state["action"])
                    if len(self.parent.action_log) > 10:
                        self.parent.action_log.pop(0)

                # draw recent actions
                for i, log_entry in enumerate(reversed(self.parent.action_log)):
                    if i >= 5:  # 5 most recent actions
                        break
                    action_text = self.parent.font.render(
                        str(log_entry), True, self.parent.TEXT_colour
                    )
                    self.parent.screen.blit(
                        action_text, (panel_x + 10, panel_y + 40 + i * 25)
                    )
            except Exception as e:
                print(f"Error drawing action: {e}")


_gui_instance = None


def initialise_gui():
    global _gui_instance
    if _gui_instance is None:
        _gui_instance = TicketToRideGUI()
    return _gui_instance.initialise()


def update_game_state(game, action=None):
    global _gui_instance
    if _gui_instance:
        _gui_instance.update_game_state(game, action)


def shutdown():
    global _gui_instance
    if _gui_instance:
        _gui_instance.shutdown()
