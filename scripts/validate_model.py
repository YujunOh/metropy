import argparse, sqlite3, sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def load_feedback(db_path):
    if not db_path.exists():
        print(f'Database not found: {db_path}')
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT boarding, alighting, hour, dow, recommended_car, '
        'actual_car, satisfaction, got_seat FROM feedback'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def run_validation(feedback, engine, auto_direction_fn):
    if not feedback:
        return {'total_feedback': 0, 'message': 'No feedback data available.'}
    n = len(feedback)
    satisfactions = [f['satisfaction'] for f in feedback]
    mean_sat = sum(satisfactions) / n
    seat_hits = sum(1 for f in feedback if f.get('got_seat', 0) == 1 or f.get('got_seat') is True)
    seat_rate = seat_hits / n
    ranks, scores_satisfied, scores_unsatisfied = [], [], []
    top1_hits, errors = 0, 0
    per_hour, per_station = {}, {}
    for f in feedback:
        per_hour.setdefault(f['hour'], []).append(f['satisfaction'])
        per_station.setdefault(f['boarding'], []).append(f['satisfaction'])
        try:
            direction = auto_direction_fn(f['boarding'], f['alighting'])
            result = engine.recommend(f['boarding'], f['alighting'], f['hour'], direction, f.get('dow', 'MON'))
            scores_df = result['scores']
            rec_car = f['recommended_car']
            car_row = scores_df[scores_df['car'] == rec_car]
            if not car_row.empty:
                rank = int(car_row.iloc[0]['rank'])
                score = float(car_row.iloc[0]['score'])
                ranks.append((rank, f['satisfaction']))
                if f['satisfaction'] >= 4:
                    scores_satisfied.append(score)
                elif f['satisfaction'] <= 2:
                    scores_unsatisfied.append(score)
            actual_car = f.get('actual_car', rec_car)
            if result['best_car'] == actual_car:
                top1_hits += 1
        except Exception:
            errors += 1
    rank_corr = None
    if len(ranks) >= 5:
        try:
            from scipy.stats import spearmanr
            r_ranks, r_sats = zip(*ranks)
            corr, pval = spearmanr(r_ranks, r_sats)
            rank_corr = {'correlation': round(float(corr), 4), 'p_value': round(float(pval), 4)}
        except ImportError:
            rank_corr = {'error': 'scipy not installed'}
    hour_summary = {h: {'count': len(s), 'avg_satisfaction': round(sum(s)/len(s), 2)} for h, s in sorted(per_hour.items())}
    station_summary = {s: {'count': len(v), 'avg_satisfaction': round(sum(v)/len(v), 2)} for s, v in sorted(per_station.items(), key=lambda x: -len(x[1]))[:10]}
    return {
        'total_feedback': n, 'mean_satisfaction': round(mean_sat, 2),
        'seat_success_rate': round(seat_rate, 4),
        'top1_accuracy': round(top1_hits / n, 4) if n > 0 else 0.0,
        'rank_correlation': rank_corr,
        'mean_score_satisfied': round(sum(scores_satisfied)/len(scores_satisfied), 2) if scores_satisfied else None,
        'mean_score_unsatisfied': round(sum(scores_unsatisfied)/len(scores_unsatisfied), 2) if scores_unsatisfied else None,
        'errors': errors, 'per_hour': hour_summary, 'per_station': station_summary,
    }

def print_report(metrics):
    print('=' * 60)
    print('SeatScore Model Validation Report')
    print('=' * 60)
    n = metrics.get('total_feedback', 0)
    if n == 0:
        print()
        print('No feedback data available.')
        print('Submit feedback via the app or /api/feedback endpoint.')
        return
    print(f'Total feedback entries: {n}')
    print(f'Mean satisfaction:      {metrics["mean_satisfaction"]}/5.0')
    print(f'Seat success rate:      {metrics["seat_success_rate"]*100:.1f}%')
    print(f'Top-1 accuracy:         {metrics["top1_accuracy"]*100:.1f}%')
    if metrics.get('rank_correlation'):
        rc = metrics['rank_correlation']
        if 'correlation' in rc:
            print(f'Rank correlation:       {rc["correlation"]} (p={rc["p_value"]})')
        elif 'error' in rc:
            print(f'Rank correlation:       N/A ({rc["error"]})')
    if metrics.get('mean_score_satisfied') is not None:
        print(f'Avg score (satisfied):    {metrics["mean_score_satisfied"]}')
    if metrics.get('mean_score_unsatisfied') is not None:
        print(f'Avg score (unsatisfied):  {metrics["mean_score_unsatisfied"]}')
    if metrics.get('errors', 0) > 0:
        print(f'Computation errors: {metrics["errors"]}')
    if metrics.get('per_hour'):
        print()
        print('--- Satisfaction by Hour ---')
        for h, data in metrics['per_hour'].items():
            bar = '*' * int(data['avg_satisfaction'] * 4)
            print(f'  {h:02d}:00  n={data["count"]:>3}  avg={data["avg_satisfaction"]:.2f}  {bar}')
    if metrics.get('per_station'):
        print()
        print('--- Satisfaction by Station (Top 10) ---')
        for s, data in metrics['per_station'].items():
            bar = '*' * int(data['avg_satisfaction'] * 4)
            print(f'  {s:<8}  n={data["count"]:>3}  avg={data["avg_satisfaction"]:.2f}  {bar}')
    print()
    print('=' * 60)
    print('Interpretation:')
    ms = metrics['mean_satisfaction']
    if ms >= 4.0:
        print('  Model is performing well (satisfaction >= 4.0)')
    elif ms >= 3.0:
        print('  Model is performing adequately (satisfaction 3.0-4.0)')
    else:
        print('  Model needs improvement (satisfaction < 3.0)')

def main():
    parser = argparse.ArgumentParser(description='Validate SeatScore model against user feedback')
    parser.add_argument('--db', type=str, default=str(PROJECT_ROOT / 'data' / 'processed' / 'feedback.db'), help='Path to feedback SQLite database')
    args = parser.parse_args()
    db_path = Path(args.db)
    print(f'Loading feedback from: {db_path}')
    feedback = load_feedback(db_path)
    print(f'Loaded {len(feedback)} feedback entries')
    if not feedback:
        print_report({'total_feedback': 0})
        return
    from src.seatscore import SeatScoreEngine
    print('Loading SeatScore engine...')
    engine = SeatScoreEngine(data_dir=str(PROJECT_ROOT / 'data' / 'processed'), raw_dir=str(PROJECT_ROOT / 'data' / 'raw'))
    engine.load_all()
    from api.dependencies import EngineRegistry
    reg = EngineRegistry()
    reg.engine = engine
    print()
    print('Running validation...')
    metrics = run_validation(feedback, engine, reg.auto_direction)
    print_report(metrics)


if __name__ == '__main__':
    main()
