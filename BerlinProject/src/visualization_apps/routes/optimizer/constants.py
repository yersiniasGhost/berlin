"""
Optimizer Constants and Configuration
Shared constants for optimizer visualization
"""

# Column metadata for custom display names and formatting
PERFORMANCE_TABLE_COLUMNS = {
    'generation': {'title': 'Gen', 'type': 'number'},
    'total_trades': {'title': 'Total Trades', 'type': 'number'},
    'winning_trades': {'title': 'Winning', 'type': 'number'},
    'losing_trades': {'title': 'Losing', 'type': 'number'},
    'total_pnl': {'title': 'Total P&L (%)', 'type': 'percentage'},
    'avg_win': {'title': 'Avg Win (%)', 'type': 'percentage'},
    'avg_loss': {'title': 'Avg Loss (%)', 'type': 'percentage'},
    'market_return': {'title': 'Market Return (%)', 'type': 'percentage'}
}


def get_table_columns_from_data(performance_metrics):
    """Auto-detect table columns from performance data"""
    if not performance_metrics:
        return []

    # Get all keys from the first data row
    sample_data = performance_metrics[0]
    columns = []

    for key in sample_data.keys():
        # Use custom metadata if available, otherwise create default
        column_info = PERFORMANCE_TABLE_COLUMNS.get(key, {
            'title': key.replace('_', ' ').title(),
            'type': 'number'  # default type
        })

        columns.append({
            'key': key,
            'title': column_info['title'],
            'type': column_info['type']
        })

    return columns
