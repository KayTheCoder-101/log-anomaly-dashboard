import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://admin:admin123@localhost:5432/logdb"
engine = create_engine(DATABASE_URL)

df = pd.read_sql("SELECT * FROM logs", engine)
print(f"Total logs: {len(df)}")
print(df.head())
print(df.describe())

print("\nStatus code counts:")
print(df["status_code"].value_counts())

plt.figure(figsize=(8, 4))
sns.histplot(df["response_time_ms"], bins=50)
plt.title("Response Time Distribution")
plt.xlabel("Response Time (ms)")
plt.savefig("response_time_dist.png")
plt.close()

plt.figure(figsize=(8, 4))
df["status_code"].value_counts().sort_index().plot(kind="bar")
plt.title("Status Code Counts")
plt.savefig("status_code_dist.png")
plt.close()

plt.figure(figsize=(8, 4))
df["source_ip"].value_counts().head(20).plot(kind="bar")
plt.title("Top 20 Source IPs by Request Count")
plt.savefig("top_ips.png")
plt.close()

print("\nSaved: response_time_dist.png, status_code_dist.png, top_ips.png")
