from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.progress import Progress, BarColumn, TimeRemainingColumn
from rich.layout import Layout

class LiveConsole:
    def __init__(self):
        self.console = Console()
        self.avg_points = 0
        self.max_points = 0
        self.live = None
        self.total_games = 0
        self.total_expected_games = 1000  # Will be updated with actual total
        self.sims_per_process = self.total_expected_games // 8
        # Dictionary to track progress of each worker
        self.worker_progress = {i: 0 for i in range(8)}
        
    def start_live(self):
        # Reset statistics at the start of a new turn
        self.avg_points = 0
        self.max_points = 0
        self.total_games = 0
        self.worker_progress = {i: 0 for i in range(8)}
        
        # Create progress and table layout
        self.progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
        )
        self.task = self.progress.add_task(
            f"[cyan]Running simulations... (0/{self.total_expected_games})", 
            total=self.total_expected_games
        )
        
        self.table = Table(title="Game Results")
        self.table.add_column("Player", justify="center", style="cyan", no_wrap=True)
        self.table.add_column("Average", justify="center", style="magenta")
        self.table.add_column("Max", justify="center", style="magenta")
        self.table.add_column("Current", justify="center", style="magenta")
        self.table.add_column("Games", justify="center", style="green")
        
        # Create a layout
        self.layout = Layout()
        self.layout_progress = Layout(name="progress", size=3)
        self.layout_table = Layout(name="table")
        self.layout.split(
            self.layout_progress,
            self.layout_table
        )
        
        # Set initial content
        self.layout_progress.update(self.progress)
        self.layout_table.update(self.table)
        
        self.live = Live(self.layout, refresh_per_second=4, console=self.console)
        self.live.start()

    def update_display(self, game_num, player_info, worker_id, total_games=None):
        """Update the display with new game results"""
        try:
            if not self.live:
                return
            
            # Update worker's progress
            self.worker_progress[worker_id] = game_num
            
            # Calculate total progress across all workers
            total_progress = sum(self.worker_progress.values())
            
            if total_games is not None:
                self.total_games = total_games
            else:
                self.total_games += 1
            
            # Update progress bar
            self.progress.update(
                self.task, 
                completed=total_progress,
                description=f"[cyan]Running simulations... ({total_progress}/{self.total_expected_games})"
            )
                
            # Update the table with the new results
            self.table = Table(title=f"Game Results (Last update: Worker {worker_id}, Sim {game_num})")
            self.table.add_column("Player", justify="center", style="cyan", no_wrap=True)
            self.table.add_column("Average", justify="center", style="magenta")
            self.table.add_column("Max", justify="center", style="magenta")
            self.table.add_column("Current", justify="center", style="magenta")
            self.table.add_column("Games", justify="center", style="green")
            
            # Calculate running average
            player_points = player_info.get('points', 0)
            self.avg_points = (self.avg_points * (self.total_games - 1) + player_points) / self.total_games if self.total_games > 0 else player_points
            self.max_points = max(self.max_points, player_points)
            
            self.table.add_row(
                player_info.get('name', ''), 
                str(round(self.avg_points, 1)), 
                str(self.max_points), 
                str(player_points),
                str(self.total_games)
            )
            
            # Update the layout
            self.layout_progress.update(self.progress)
            self.layout_table.update(self.table)
            
            self.live.update(self.layout)
        except Exception as e:
            print(f"Error updating display: {e}")

    def stop(self):
        """Stop the live display"""
        if self.live:
            self.progress.update(self.task, completed=self.total_expected_games)
            self.live.stop()
            self.live = None