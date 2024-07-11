INITIAL_LEVEL_POINTS_NEEDED = 1000  # Starting with a higher initial value
INITIAL_LEVEL = 1

def calculate_level_points(POINTS_NEEDED, CURRENT_LEVEL, growth_factor):
    if CURRENT_LEVEL == 1:
        return INITIAL_LEVEL_POINTS_NEEDED
    else:
        return round(POINTS_NEEDED * growth_factor)

# Calculate total points needed to reach a certain level
def total_points_to_reach_level(target_level, growth_factor):
    total_points = 0
    points_needed = INITIAL_LEVEL_POINTS_NEEDED
    for level in range(2, target_level + 1):
        points_needed = calculate_level_points(points_needed, level, growth_factor)
        total_points += points_needed
    return total_points

# Adjust growth factor to fit the goal
def find_optimal_growth_factor(target_levels, target_points):
    growth_factor = 1.01
    while True:
        match = True
        for target_level, target_point in zip(target_levels, target_points):
            total_points = total_points_to_reach_level(target_level, growth_factor)
            if abs(total_points - target_point) > target_point * 0.01:  # Allow 1% tolerance
                match = False
                break
        if match:
            break
        growth_factor += 0.001
    return growth_factor - 0.001  # Step back to the last valid growth factor

# Target levels and their corresponding total points
target_levels = [10, 100, 300]
target_points = [12000, 97000, 600000]

# Calculate the optimal growth factor
optimal_growth_factor = find_optimal_growth_factor(target_levels, target_points)

# Print the optimal growth factor
print(f"Optimal growth factor: {optimal_growth_factor:.4f}")

# Calculate points needed for each level incrementally
def points_needed_per_level(target_level, growth_factor):
    points_per_level = []
    points_needed = INITIAL_LEVEL_POINTS_NEEDED
    for level in range(1, target_level):
        next_level_points = calculate_level_points(points_needed, level, growth_factor)
        points_per_level.append((level, next_level_points))
        points_needed = next_level_points
    return points_per_level

# Print points needed for each level from 1 to target level
target_level = 500
points_per_level = points_needed_per_level(target_level, optimal_growth_factor)
for level, points in points_per_level:
    print(f"Points needed from level {level} to {level + 1}: {points} points")
