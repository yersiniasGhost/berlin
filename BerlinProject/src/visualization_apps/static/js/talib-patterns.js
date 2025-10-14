/**
 * TA-Lib Candlestick Pattern Reference
 * Patterns categorized by the signal direction they can provide
 *
 * BULLISH patterns: Can return positive values (bullish-only OR bidirectional)
 * BEARISH patterns: Can return negative values (bearish-only OR bidirectional)
 *
 * Bidirectional patterns appear in BOTH lists because they can signal either direction.
 * The indicator code filters based on the sign of the TA-Lib return value.
 */

// Patterns that can return POSITIVE values (bullish-only + bidirectional)
const BULLISH_PATTERNS = [
    // Bullish-only patterns
    "CDL3STARSINSOUTH",
    "CDL3WHITESOLDIERS",
    "CDLCONCEALBABYSWALL",
    "CDLHAMMER",
    "CDLHOMINGPIGEON",
    "CDLINVERTEDHAMMER",
    "CDLLADDERBOTTOM",
    "CDLMATCHINGLOW",
    "CDLMORNINGDOJISTAR",
    "CDLMORNINGSTAR",
    "CDLPIERCING",
    "CDLSTICKSANDWICH",
    "CDLTAKURI",
    "CDLUNIQUE3RIVER",

    // Bidirectional patterns (can be bullish or bearish based on context)
    "CDL3INSIDE",
    "CDL3LINESTRIKE",
    "CDL3OUTSIDE",
    "CDLABANDONEDBABY",
    "CDLADVANCEBLOCK",
    "CDLBELTHOLD",
    "CDLBREAKAWAY",
    "CDLCLOSINGMARUBOZU",
    "CDLCOUNTERATTACK",
    "CDLDOJI",
    "CDLDOJISTAR",
    "CDLDRAGONFLYDOJI",
    "CDLENGULFING",
    "CDLGAPSIDESIDEWHITE",
    "CDLGRAVESTONEDOJI",
    "CDLHARAMI",
    "CDLHARAMICROSS",
    "CDLHIGHWAVE",
    "CDLHIKKAKE",
    "CDLHIKKAKEMOD",
    "CDLINNECK",
    "CDLKICKING",
    "CDLKICKINGBYLENGTH",
    "CDLLONGLEGGEDDOJI",
    "CDLLONGLINE",
    "CDLMARUBOZU",
    "CDLMATHOLD",
    "CDLONNECK",
    "CDLRICKSHAWMAN",
    "CDLRISEFALL3METHODS",
    "CDLSEPARATINGLINES",
    "CDLSHORTLINE",
    "CDLSPINNINGTOP",
    "CDLSTALLEDPATTERN",
    "CDLTASUKIGAP",
    "CDLTHRUSTING",
    "CDLTRISTAR",
    "CDLXSIDEGAP3METHODS"
];

// Patterns that can return NEGATIVE values (bearish-only + bidirectional)
const BEARISH_PATTERNS = [
    // Bearish-only patterns
    "CDL2CROWS",
    "CDL3BLACKCROWS",
    "CDLDARKCLOUDCOVER",
    "CDLEVENINGDOJISTAR",
    "CDLEVENINGSTAR",
    "CDLHANGINGMAN",
    "CDLIDENTICAL3CROWS",
    "CDLSHOOTINGSTAR",
    "CDLUPSIDEGAP2CROWS",

    // Bidirectional patterns (can be bullish or bearish based on context)
    "CDL3INSIDE",
    "CDL3LINESTRIKE",
    "CDL3OUTSIDE",
    "CDLABANDONEDBABY",
    "CDLADVANCEBLOCK",
    "CDLBELTHOLD",
    "CDLBREAKAWAY",
    "CDLCLOSINGMARUBOZU",
    "CDLCOUNTERATTACK",
    "CDLDOJI",
    "CDLDOJISTAR",
    "CDLDRAGONFLYDOJI",
    "CDLENGULFING",
    "CDLGAPSIDESIDEWHITE",
    "CDLGRAVESTONEDOJI",
    "CDLHARAMI",
    "CDLHARAMICROSS",
    "CDLHIGHWAVE",
    "CDLHIKKAKE",
    "CDLHIKKAKEMOD",
    "CDLINNECK",
    "CDLKICKING",
    "CDLKICKINGBYLENGTH",
    "CDLLONGLEGGEDDOJI",
    "CDLLONGLINE",
    "CDLMARUBOZU",
    "CDLMATHOLD",
    "CDLONNECK",
    "CDLRICKSHAWMAN",
    "CDLRISEFALL3METHODS",
    "CDLSEPARATINGLINES",
    "CDLSHORTLINE",
    "CDLSPINNINGTOP",
    "CDLSTALLEDPATTERN",
    "CDLTASUKIGAG",
    "CDLTHRUSTING",
    "CDLTRISTAR",
    "CDLXSIDEGAP3METHODS"
];

/**
 * Get available patterns based on trend type
 * @param {string} trend - "bullish" or "bearish"
 * @returns {Array<string>} - Sorted list of pattern names
 */
function getPatternsByTrend(trend) {
    if (trend === 'bullish') {
        return [...BULLISH_PATTERNS].sort();
    } else if (trend === 'bearish') {
        return [...BEARISH_PATTERNS].sort();
    }
    return [];
}
