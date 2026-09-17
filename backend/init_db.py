from migrate import upgrade


if __name__ == "__main__":
    upgrade(initialize=True)
    print("database tables and guards initialized")
