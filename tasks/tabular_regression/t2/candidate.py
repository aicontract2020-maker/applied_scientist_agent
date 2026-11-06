def augment(row):
    return [abs(row[9]) / max(max(abs(row[6]), abs(row[9])), 0.000001)]