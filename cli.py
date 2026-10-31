def select_exercise(quarterly):

    # Get unique exercises
    exercises = (
        quarterly[["exercise_id", "exercise_title"]]
        .drop_duplicates()
        .copy()
    )

    # Display the big three first
    priority = {
        "Bench Press (Barbell)": 0,
        "Squat (Barbell)": 1,
        "Deadlift (Barbell)": 2
    }

    exercises["sort_order"] = (
        exercises["exercise_title"]
        .map(priority)
        .fillna(3)
    )

    exercises = (
        exercises
        .sort_values(["sort_order", "exercise_title"])
        .reset_index(drop=True)
    )

    print("\n===== HEVY STRENGTH INSIGHTS =====")
    print("\nSelect an exercise:\n")

    for index, row in exercises.iterrows():
        print(f"{index + 1}. {row['exercise_title']}")

    # Validate user selection
    while True:
        try:
            choice = int(input("\nEnter exercise number: "))

            if 1 <= choice <= len(exercises):
                break

            print("Please enter a valid exercise number.")

        except ValueError:
            print("Please enter a number.")

    # Retrieve the selected exercise
    selected = exercises.iloc[choice - 1]

    print(f"\nGenerating quarterly analysis for {selected['exercise_title']}...")

    return selected["exercise_id"]