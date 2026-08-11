import json
import os

import psycopg2
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://admin:admin123@localhost:5432/logdb"
)
GROUND_TRUTH_PATH = os.environ.get("GROUND_TRUTH_PATH", "/data/ground_truth.jsonl")


def load_ground_truth(path):
    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line))
    return records


def fetch_predictions(conn, ids):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, is_anomaly, anomaly_score, lstm_is_anomaly, lstm_anomaly_score
               FROM logs WHERE id = ANY(%s)""",
            (ids,),
        )
        return {
            row[0]: {
                "is_anomaly": row[1],
                "anomaly_score": row[2],
                "lstm_is_anomaly": row[3],
                "lstm_anomaly_score": row[4],
            }
            for row in cur.fetchall()
        }


def report(name, y_true, y_pred):
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)

    print(f"\n=== {name} ===")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1 score:  {f1:.3f}")
    print(f"Confusion matrix (rows=true, cols=predicted):")
    print(f"                predicted_normal  predicted_anomaly")
    print(f"true_normal     {cm[0][0]:>16}  {cm[0][1]:>17}")
    print(f"true_anomaly    {cm[1][0]:>16}  {cm[1][1]:>17}")


def main():
    ground_truth = load_ground_truth(GROUND_TRUTH_PATH)
    ids = [r["id"] for r in ground_truth]

    conn = psycopg2.connect(DATABASE_URL)
    predictions = fetch_predictions(conn, ids)
    conn.close()

    y_true, y_pred_if, y_pred_lstm = [], [], []
    missing_if, missing_lstm = 0, 0

    for r in ground_truth:
        pred = predictions.get(r["id"])
        if pred is None:
            missing_if += 1
            missing_lstm += 1
            continue

        if pred["is_anomaly"] is None:
            missing_if += 1
        else:
            y_true.append(r["true_label"])
            y_pred_if.append(1 if pred["is_anomaly"] else 0)

        if pred["lstm_is_anomaly"] is None:
            missing_lstm += 1

    # Rebuild y_true/y_pred_lstm separately since IF and LSTM can have
    # different missing rows (e.g. LSTM needs 20+ rows of history).
    y_true_lstm, y_pred_lstm = [], []
    for r in ground_truth:
        pred = predictions.get(r["id"])
        if pred is None or pred["lstm_is_anomaly"] is None:
            continue
        y_true_lstm.append(r["true_label"])
        y_pred_lstm.append(1 if pred["lstm_is_anomaly"] else 0)

    print(f"Total ground-truth rows: {len(ground_truth)}")
    print(f"Isolation Forest — missing/unscored: {missing_if}, evaluated: {len(y_true)}")
    print(f"LSTM — missing/unscored: {missing_lstm}, evaluated: {len(y_true_lstm)}")

    if y_true:
        report("Isolation Forest", y_true, y_pred_if)
    else:
        print("\nNo Isolation Forest predictions to evaluate.")

    if y_true_lstm:
        report("LSTM Autoencoder", y_true_lstm, y_pred_lstm)
    else:
        print("\nNo LSTM predictions to evaluate.")


if __name__ == "__main__":
    main()
