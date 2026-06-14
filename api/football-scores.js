export default async function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const API_KEY = process.env.FOOTBALL_DATA_API_KEY;
  if (!API_KEY) {
    return res.status(500).json({ error: 'FOOTBALL_DATA_API_KEY not set' });
  }

  const headers = { 'X-Auth-Token': API_KEY };

  const today = new Date();
  const from = new Date(today); from.setDate(today.getDate() - 1);
  const to = new Date(today); to.setDate(today.getDate() + 3);
  const fmt = d => d.toISOString().split('T')[0];
  const dateRange = `dateFrom=${fmt(from)}&dateTo=${fmt(to)}`;

  // WC = FIFA World Cup 2026, PL = Premier League, PD = La Liga,
  // BL1 = Bundesliga, SA = Serie A, FL1 = Ligue 1
  const LEAGUE_CODES = ['PL', 'PD', 'BL1', 'SA', 'FL1'];

  try {
    // Fetch World Cup matches
    const wcRes = await fetch(
      `https://api.football-data.org/v4/competitions/WC/matches?${dateRange}`,
      { headers }
    );
    const wcData = wcRes.ok ? await wcRes.json() : { matches: [] };
    const wcMatches = (wcData.matches || []).map(m => ({
      ...m,
      _competition: 'FIFA World Cup 2026',
      _isWorldCup: true
    }));

    // Fetch league matches in parallel
    const leagueResults = await Promise.allSettled(
      LEAGUE_CODES.map(code =>
        fetch(
          `https://api.football-data.org/v4/competitions/${code}/matches?${dateRange}`,
          { headers }
        )
          .then(r => r.ok ? r.json() : { matches: [] })
          .then(d => (d.matches || []).map(m => ({
            ...m,
            _competition: code,
            _isWorldCup: false
          })))
      )
    );

    const leagueMatches = leagueResults
      .filter(r => r.status === 'fulfilled')
      .flatMap(r => r.value);

    // Sort each group by utcDate
    const sort = arr => arr.sort((a, b) => new Date(a.utcDate) - new Date(b.utcDate));

    return res.status(200).json({
      worldCup: sort(wcMatches),
      leagues: sort(leagueMatches),
      hasWorldCup: wcMatches.length > 0
    });

  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
