import matplotlib.pyplot as plt
import pandas as pd

def visualise_value(dataframe : pd.DataFrame):
    portfolio_value = dataframe[dataframe["name"] == "Сумма"]
    plt.figure(figsize=(12, 8))
    plt.plot(portfolio_value["datetime"], portfolio_value["value"], marker='o')
    plt.title("Portfolio Value")
    plt.xlabel("Date")
    plt.ylabel("Price (RUB)")
    plt.grid(True)
    plt.show()

def main():
    df = pd.read_csv("portfolio_history.csv")
    visualise_value(df)

if __name__ == "__main__":
    main()