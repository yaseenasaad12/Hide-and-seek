import numpy as np
import random
from scipy.optimize import linprog
import json


class HideAndSeekGame:
    def __init__(self, world_size, use_proximity=False, is_2d=False):
        self.world_size = world_size
        self.use_proximity = use_proximity
        self.is_2d = is_2d
        
        # Calculate grid dimensions for 2D worlds
        if is_2d:
            self.rows = int(np.sqrt(world_size))
            while world_size % self.rows != 0:
                self.rows -= 1
            self.cols = world_size // self.rows
        else:
            self.rows = 1
            self.cols = world_size
            
        self.reset_game()
    
    def reset_game(self):
        self.place_types = self.generate_place_types()
        self.payoff_matrix = self.generate_base_payoff_matrix() 
        self.human_score = 0
        self.computer_score = 0
        self.rounds_played = 0
        self.human_wins = 0
        self.computer_wins = 0
        self.calculate_optimal_strategies()
        
    def reset_scores(self):
        self.human_score = 0
        self.computer_score = 0
        self.rounds_played = 0
        self.human_wins = 0
        self.computer_wins = 0


    def generate_place_types(self):
        """Generate place types ensuring at least one of each type"""
        # First ensure we have at least one of each type
        place_types = [0, 1, 2]  # One hard, one neutral, one easy
        
        # Fill remaining positions with weighted random choices
        remaining = self.world_size - 3
        if remaining > 0:
            type_weights = [0.3, 0.4, 0.3]  # Hard, Neutral, Easy
            place_types.extend(random.choices([0, 1, 2], weights=type_weights, k=remaining))
        
        # Shuffle the positions
        random.shuffle(place_types)
        return place_types
    
    def calculate_distance(self, pos1, pos2):
        if self.is_2d:
            # Convert linear positions to 2D coordinates
            row1, col1 = pos1 // self.cols, pos1 % self.cols
            row2, col2 = pos2 // self.cols, pos2 % self.cols
            return abs(row1 - row2) + abs(col1 - col2)  # Manhattan distance for 2D
        else:
            return abs(pos1 - pos2)  # Linear distance for 1D 
    
    def position_to_coords(self, pos):
        """Convert a linear position to coordinates string"""
        if self.is_2d:
            col ,row = pos // self.cols, pos % self.cols
            return f"({row+1},{col+1})"
        else:
            return f"{pos+1}"
    
    def get_proximity_multiplier(self, pos1, pos2):
        distance = self.calculate_distance(pos1, pos2)
        
        if distance == 1:
            return 0.5  # If one cell away, multiply by 0.5
        elif distance == 2:
            return 0.75  # If two cells away, multiply by 0.75
        else:
            return 1.0  # Otherwise, no change 
    
    def generate_base_payoff_matrix(self):
            """Generate base payoff matrix, applying proximity effects if enabled"""
            matrix = np.zeros((self.world_size, self.world_size))
            
            # Payoff definitions (found_payoff, not_found_payoff)
            payoffs = {
                0: (-3, 1),  # hard for seeker
                1: (-1, 1),   # neutral for seeker
                2: (-1, 2)    # easy for seeker
            }

            for h in range(self.world_size):
                for s in range(self.world_size):
                    if h == s:  # Seeker found hider - no proximity effect
                        matrix[h, s] = payoffs[self.place_types[h]][0]
                    else:  # Seeker didn't find hider
                        base_payoff = payoffs[self.place_types[h]][1]
                        
                        if self.use_proximity:
                            # Apply proximity multiplier to the not-found payoff
                            multiplier = self.get_proximity_multiplier(h, s)
                            matrix[h, s] = base_payoff * multiplier
                        else:
                            matrix[h, s] = base_payoff
                                
            return matrix
    
    """ def apply_proximity_effects(self):
        proximity_matrix = np.zeros((self.world_size, self.world_size))
        
        for h in range(self.world_size):
            for s in range(self.world_size):
                if h == s:  # Seeker found hider - same as base matrix
                    proximity_matrix[h, s] = self.payoff_matrix[h, s]
                else:  # Apply proximity effects when seeker doesn't find hider
                    multiplier = self.get_proximity_multiplier(h, s)
                    proximity_matrix[h, s] = self.payoff_matrix[h, s] * multiplier
                    
        return proximity_matrix   """
    
    
    def calculate_optimal_strategies(self):
        # For hider (row player) - maximin
        # Decision variables: [x1, x2, ..., xn, v] where v is the value of the game
        c = np.zeros(self.world_size + 1)
        c[-1] = -1  # Maximize v (negate for minimization)
        
        # Constraints: x1*A_1j + x2*A_2j + ... + xn*A_nj - v ≥ 0 for all j
        A_ub = np.column_stack([-self.payoff_matrix.T, np.ones(self.world_size)])
        b_ub = np.zeros(self.world_size)
        
        # Sum of probabilities = 1, excluding v
        A_eq = np.zeros((1, self.world_size + 1))
        A_eq[0, :-1] = 1
        b_eq = np.ones(1)
        
        # All probabilities non-negative, v unconstrained
        bounds = [(0, None)] * self.world_size + [(None, None)]
        
        hider_result = linprog(
            c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
            bounds=bounds, method='highs'
        )
        
        if hider_result.success:
            self.hider_probabilities = hider_result.x[:-1]  # Exclude v
            game_value = -hider_result.fun  # The value of the game
        
        # For seeker (column player) - minimax
        # Decision variables: [y1, y2, ..., yn, u] where u is the value of the game
        c = np.zeros(self.world_size + 1)
        c[-1] = 1  # Minimize u
        
        # Constraints: A_i1*y1 + A_i2*y2 + ... + A_in*yn - u ≤ 0 for all i
        A_ub = np.column_stack([self.payoff_matrix, -np.ones(self.world_size)])
        b_ub = np.zeros(self.world_size)
        
        # Sum of probabilities = 1, excluding u
        A_eq = np.zeros((1, self.world_size + 1))
        A_eq[0, :-1] = 1
        b_eq = np.ones(1)
        
        # All probabilities non-negative, u unconstrained
        bounds = [(0, None)] * self.world_size + [(None, None)]
        
        seeker_result = linprog(
            c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
            bounds=bounds, method='highs'
        )
        
        if seeker_result.success:
            self.seeker_probabilities = seeker_result.x[:-1]  # Exclude u
            # The values should be approximately equal
            assert abs(game_value - seeker_result.fun) < 1e-6
    
    def print_strategy_debug_info(self):
        """Print debug information about strategies"""
        print("\n=== Strategy Debug Info ===")
        print("Place Types:", [['Hard','Neutral','Easy'][t] for t in self.place_types])
        
        # Print place types in 2D grid format if is_2d
        if self.is_2d:
            print("\nGrid Layout of Place Types:")
            for row in reversed(range(self.rows)):
                row_str = ""
                for col in range(self.cols):
                    pos = row * self.cols + col
                    place_type = ['H','N','E'][self.place_types[pos]]
                    row_str += f"{place_type} "
                print(row_str)
        
        print("\nPayoff Matrix (Hider's perspective) - USED FOR GAME SCORING:")
        for i, row in enumerate(self.payoff_matrix):
            pos_str = self.position_to_coords(i)
            print(f"Pos {pos_str:>5} ({['Hard','Neutral','Easy'][self.place_types[i]]}):", 
                  " ".join(f"{x:5.3f}" for x in row))
        
        """ if self.use_proximity:
            print("\nProximity Matrix (WITH PROXIMITY EFFECTS APPLIED):")
            for i, row in enumerate(self.proximity_matrix):
                pos_str = self.position_to_coords(i)
                print(f"Pos {pos_str:>5} ({['Hard','Neutral','Easy'][self.place_types[i]]}):", 
                    " ".join(f"{x:5.1f}" for x in row)) """
        
        print("\nHider Probabilities:")
        for i, p in enumerate(self.hider_probabilities):
            pos_str = self.position_to_coords(i)
            print(f"Pos {pos_str:>5}: {p:.2%}")
        
        print("\nSeeker Probabilities:")
        for i, p in enumerate(self.seeker_probabilities):
            pos_str = self.position_to_coords(i)
            print(f"Pos {pos_str:>5}: {p:.2%}")
    
    def visualize_grid(self, hider_pos=None, seeker_pos=None):
        """Visualize the 2D grid with place types and player positions"""
        if not self.is_2d:
            print("Grid visualization only available in 2D mode")
            return
        
        # Type representation: H(ard), N(eutral), E(asy)
        type_chars = ['H', 'N', 'E']
        
        print("\n  " + " ".join(f"{i+1}" for i in range(self.cols)))
        print("  " + "-" * (self.cols * 2 - 1))
        
        for row in reversed(range(self.rows)):
            row_str = f"{row+1}|"
            for col in range(self.cols):
                pos = row * self.cols + col
                cell = type_chars[self.place_types[pos]]
                
                # Add player markers
                if pos == hider_pos and pos == seeker_pos:
                    cell = "X"  # Both at same position
                elif pos == hider_pos:
                    cell = "H"  # Hider
                elif pos == seeker_pos:
                    cell = "S"  # Seeker
                
                row_str += f"{cell} "
            print(row_str)
    
    def play_round(self, human_move):
        """Play one round of the game"""
        computer_move = self.get_computer_move()

        if self.human_role == "hider":
            hider_pos, seeker_pos = human_move, computer_move
        else:
            hider_pos, seeker_pos = computer_move, human_move


        # Determine if proximity score applies
        """ use_proximity = self.use_proximity and hider_pos != seeker_pos
        proximity_score = self.proximity_matrix[hider_pos, seeker_pos] if use_proximity else None
        proximity_multiplier = self.get_proximity_multiplier(hider_pos, seeker_pos) if use_proximity else None
        """
        # Update scores based on actual used score (proximity if enabled)
        final_score = self.payoff_matrix[hider_pos, seeker_pos]
        distance = self.calculate_distance(hider_pos, seeker_pos) if self.use_proximity else None
        self.update_scores(final_score)

        self.rounds_played += 1
        
        # Visualize the grid if in 2D mode
        if self.is_2d:
            self.visualize_grid(hider_pos, seeker_pos)
            
        return self.format_result(
            final_score, hider_pos, seeker_pos, distance
        ), hider_pos, seeker_pos

    def update_scores(self, score):
        """Update scores in a zero-sum fashion"""
        if self.human_role == "hider":
            self.human_score += score
            self.computer_score -= score
        else:
            self.human_score -= score
            self.computer_score += score

        if score > 0:
            if self.human_role == "hider":
                self.human_wins += 1
            else:
                self.computer_wins += 1
        else:
            if self.human_role == "hider":
                self.computer_wins += 1
            else:
                self.human_wins += 1

    
    def format_result(self, score, hider_pos, seeker_pos, distance=None):
        place_type = ['Hard', 'Neutral', 'Easy'][self.place_types[hider_pos]]
        hider_coords = self.position_to_coords(hider_pos)
        seeker_coords = self.position_to_coords(seeker_pos)
        
        # Create a detailed message that explains proximity scoring if applicable
        proximity_detail = ""
        if self.use_proximity and hider_pos != seeker_pos:
            multiplier = self.get_proximity_multiplier(hider_pos, seeker_pos)
            proximity_detail = f" (Distance: {distance}, Multiplier: {multiplier:.2f})"
        
        if self.human_role == "hider":
            if hider_pos == seeker_pos:
                return f"Computer found you at {hider_coords} [{place_type}]. You lose {abs(score):.2f} points, computer gains {abs(score):.2f} points."
            else:
                return f"You win +{score:.2f} points, computer loses {abs(score):.2f} points{proximity_detail} (Hide at {hider_coords} [{place_type}], computer searched at {seeker_coords})"
        else:
            if hider_pos == seeker_pos:
                return f"You found hider at {hider_coords} [{place_type}]. You gain +{abs(score):.2f} points, computer loses {abs(score):.2f} points."
            else:
                return f"Computer wins {abs(score):.2f} points, you lose {abs(score):.2f} points{proximity_detail} (Computer hide at {hider_coords} [{place_type}], you searched at {seeker_coords})"
        
    def get_computer_move(self):
        """Get computer's move based on optimal strategy"""
        probs = self.seeker_probabilities if self.human_role == "hider" else self.hider_probabilities
        return np.random.choice(self.world_size, p=probs)
    
    def convert_input_to_position(self, input_str):
        """Convert user input to game position based on game dimension"""
        try:
            if self.is_2d:
                # For 2D, accept inputs like "2,3" or "(2,3)" for row 2, column 3
                # Remove parentheses and split by comma
                clean_input = input_str.replace("(", "").replace(")", "").strip()
                parts = clean_input.split(",")
                
                if len(parts) != 2:
                    return None, "Please enter coordinates as 'row,column' (e.g., '2,3')"
                
                try:
                    row = int(parts[0].strip()) - 1  # Convert to 0-indexed
                    col = int(parts[1].strip()) - 1  # Convert to 0-indexed
                    
                    if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
                        return None, f"Coordinates out of range. Please enter values between (1,1) and ({self.rows},{self.cols})"
                    
                    pos = row * self.cols + col
                    return pos, None
                
                except ValueError:
                    return None, "Invalid coordinates. Please enter numeric values (e.g., '2,3')"
            else:
                # For 1D, just accept a single number
                try:
                    pos = int(input_str.strip()) - 1  # Convert to 0-indexed
                    
                    if pos < 0 or pos >= self.world_size:
                        return None, f"Position out of range. Please enter a value between 1 and {self.world_size}"
                    
                    return pos, None
                
                except ValueError:
                    return None, "Invalid position. Please enter a numeric value"
        except Exception as e:
            return None, f"Error processing input: {str(e)}"
    
    def run_simulation(self, rounds=100, output_file="simulation_results.txt"):
        """Run automated simulation and save detailed results to a text file (zero-sum)"""
        # Save original state
        original_state = {
            'human_score': self.human_score,
            'computer_score': self.computer_score,
            'rounds_played': self.rounds_played,
            'human_wins': self.human_wins,
            'computer_wins': self.computer_wins
        }
        
        # Reset temporary state
        self.human_score = self.computer_score = 0
        self.human_wins = self.computer_wins = 0
        self.rounds_played = 0

        hider_position_counts = {pos: 0 for pos in range(self.world_size)}
        seeker_position_counts = {pos: 0 for pos in range(self.world_size)}
        
        # Prepare to write to output file
        with open(output_file, 'w') as f:
            f.write(f"Hide and Seek Simulation - {rounds} rounds (Zero-Sum)\n")
            f.write(f"World Size: {self.world_size}\n")
            f.write(f"Proximity Effects: {'ON' if self.use_proximity else 'OFF'}\n")
            f.write(f"Grid: {'2D' if self.is_2d else '1D'}\n")
            f.write(f"Human Role: {self.human_role}\n\n")
            
            f.write("=== Round-by-Round Results ===\n")
            
            for round_num in range(1, rounds + 1):
                # Get moves
                probs = self.seeker_probabilities if self.human_role == "seeker" else self.hider_probabilities
                human_move = np.random.choice(self.world_size, p=probs)
                computer_move = self.get_computer_move()
            
                
                # Determine positions based on roles
                if self.human_role == "hider":
                    hider_pos, seeker_pos = human_move, computer_move
                else:
                    hider_pos, seeker_pos = computer_move, human_move
                
                hider_position_counts[hider_pos] += 1
                seeker_position_counts[seeker_pos] += 1 

                final_score = self.payoff_matrix[hider_pos, seeker_pos]
                distance = self.calculate_distance(hider_pos, seeker_pos) if self.use_proximity and hider_pos != seeker_pos else None

                
                # Update scores (zero-sum)
                self.update_scores(final_score)
                self.rounds_played += 1
                
                # Determine winner
                if self.human_role == "hider":
                    human_won = final_score > 0
                else:
                    human_won = final_score < 0
                
                # Write round details to file
                f.write(f"\nRound {round_num}:\n")
                f.write(f"  Hider position: {self.position_to_coords(hider_pos)} ({['Hard','Neutral','Easy'][self.place_types[hider_pos]]})\n")
                f.write(f"  Seeker position: {self.position_to_coords(seeker_pos)}\n")
                
                if hider_pos == seeker_pos:
                    f.write("  RESULT: Hider found!\n")
                else:
                    if self.use_proximity:
                         multiplier = self.get_proximity_multiplier(hider_pos, seeker_pos)
                         f.write(f"  Distance: {distance}, Multiplier: {multiplier:.2f}\n")
                    f.write("  RESULT: Hider not found\n")
                
                f.write(f"  Human points: {final_score if self.human_role == 'hider' else -final_score:.1f}\n")
                f.write(f"  Computer points: {-final_score if self.human_role == 'hider' else final_score:.1f}\n")
                f.write(f"  Winner: {'Human' if human_won else 'Computer'}\n")
                f.write(f"  Total points of Human: {self.human_score:.3f}\n")
                f.write(f"  Total points of Computer: {self.computer_score:.3f}\n")
                # Write summary to file
            f.write("\n=== Simulation Summary ===\n")
            f.write(f"Total Rounds: {rounds}\n")
            f.write(f"Human Score: {self.human_score:.3f}\n")
            f.write(f"Computer Score: {self.computer_score:.3f}\n")
            f.write(f"Human Wins: {self.human_wins} ({self.human_wins/rounds:.3%})\n")
            f.write(f"Computer Wins: {self.computer_wins} ({self.computer_wins/rounds:.3%})\n")
            f.write(f"Net Score (Human - Computer): {self.human_score - self.computer_score:.3f}\n")


        print("\n=== Hider Position Counts ===")
        for pos, count in hider_position_counts.items():
            coords = self.position_to_coords(pos)
            place_type = ['Hard', 'Neutral', 'Easy'][self.place_types[pos]]
            print(f"Position {pos} ({coords} - {place_type}): {count} times")

    # Print SEEKER position stats
        print("\n=== Seeker Position Counts ===")
        for pos, count in seeker_position_counts.items():
            coords = self.position_to_coords(pos)
            place_type = ['Hard', 'Neutral', 'Easy'][self.place_types[pos]]
            print(f"Position {pos} ({coords} - {place_type}): {count} times")


        # Print summary to console
        print("\n=== Simulation Complete ===")
        print(f"Results saved to {output_file}")
        print(f"Human Wins: {self.human_wins} ({self.human_wins/rounds:.3%})")
        print(f"Computer Wins: {self.computer_wins} ({self.computer_wins/rounds:.3%})")
        print(f"Human Score: {self.human_score:.3f}")
        print(f"Computer Score: {self.computer_score:.3f}")
        print(f"Net Score (Human - Computer): {self.human_score - self.computer_score:.3f}")
        
        results = {
            'human_score': self.human_score,
            'computer_score': self.computer_score,
            'human_wins': self.human_wins,
            'computer_wins': self.computer_wins,
            'output_file': output_file
        }
        
        # Restore original state
        for key, val in original_state.items():
            setattr(self, key, val)

        return results
    
    def save_state(self, filename):
        """Save game state to file"""
        state = {
            'world_size': self.world_size,
            'use_proximity': self.use_proximity,
            'is_2d': self.is_2d,
            'rows': self.rows,
            'cols': self.cols,
            'place_types': self.place_types,
            'payoff_matrix': self.payoff_matrix.tolist(),
            #'proximity_matrix': self.proximity_matrix.tolist() if self.use_proximity else None,
            'human_role': self.human_role,
            'human_score': self.human_score,
            'computer_score': self.computer_score,
            'rounds_played': self.rounds_played,
            'human_wins': self.human_wins,
            'computer_wins': self.computer_wins
        }
        
        with open(filename, 'w') as f:
            json.dump(state, f)
    
    def load_state(self, filename):
        """Load game state from file"""
        with open(filename, 'r') as f:
            state = json.load(f)
        
        self.world_size = state['world_size']
        self.use_proximity = state['use_proximity']
        self.is_2d = state['is_2d']
        self.rows = state.get('rows', int(np.sqrt(self.world_size)) if self.is_2d else 1)
        self.cols = state.get('cols', self.world_size // self.rows if self.is_2d else self.world_size)
        self.place_types = state['place_types']
        self.payoff_matrix = np.array(state['payoff_matrix'])
        
        """ if self.use_proximity and state.get('proximity_matrix'):
            self.proximity_matrix = np.array(state['proximity_matrix'])
        else:
            self.proximity_matrix = self.apply_proximity_effects() if self.use_proximity else self.payoff_matrix.copy() """
            
        self.human_role = state['human_role']
        self.human_score = state['human_score']
        self.computer_score = state['computer_score']
        self.rounds_played = state['rounds_played']
        self.human_wins = state['human_wins']
        self.computer_wins = state['computer_wins']
        
        self.calculate_optimal_strategies()


    def create_proximity_weight_matrix(self, seeker_position):
        """Create a weight matrix based on proximity to seeker position"""
        weight_matrix = np.ones((self.rows, self.cols))  # Default multiplier is 1
        
        # Convert seeker position to 2D coordinates
        seeker_row, seeker_col = seeker_position // self.cols, seeker_position % self.cols
        
        # Apply proximity penalties based on Manhattan distance
        for i in range(self.rows):
            for j in range(self.cols):
                manhattan_distance = abs(i - seeker_row) + abs(j - seeker_col)
                
                if manhattan_distance == 1:
                    weight_matrix[i, j] = 0.5  # One cell away
                elif manhattan_distance == 2:
                    weight_matrix[i, j] = 0.75  # Two cells away
                # Otherwise, keep the default multiplier of 1
        
        return weight_matrix
    
    

if __name__ == "__main__":
    # Example usage with 2D grid and proximity effects enabled
    game = HideAndSeekGame(world_size=9, use_proximity=False, is_2d=True)
    game.human_role = "hider"
    
    # Print debug info to see the payoff matrix with proximity effects
    game.print_strategy_debug_info()
    
    # Example: Demonstrate grid visualization
    print("\nInitial grid:")
    game.visualize_grid()
    
    # Example: Human hides at position (2,2)
    # Convert this to linear position: row * cols + col = 1 * 3 + 1 = 4 (0-indexed)
    human_move = 4  # Position (2,2) in a 3x3 grid
    result, hider_pos, seeker_pos = game.play_round(human_move)
    print("\nExample round result:")
    print(result)
