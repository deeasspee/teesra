export default async function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const API_KEY = process.env.FOOTBALL_DATA_API_KEY;
  if (!API_KEY) {
    return res.status(500).json({ error: 'FOOTBALL_DATA_API_KEY not set' });
  }

  const headers = { 'X-Auth-Token': API_KEY };

  // Date window: yesterday to 7 days ahead (to always show upcoming if nothing live)
  const today = new Date();
  const from = new Date(today); from.setDate(today.getDate() - 1);
  const to = new Date(today); to.setDate(today.getDate() + 7);
  const fmt = d => d.toISOString().split('T')[0];
  const dateRange = `dateFrom=${fmt(from)}&dateTo=${fmt(to)}`;

  const LEAGUE_CODES = ['PL', 'PD', 'BL1', 'SA', 'FL1', 'CL'];

  async function fetchComp(code) {
    try {
      const r = await fetch(
        `https://api.football-data.org/v4/competitions/${code}/matches?${dateRange}`,
        { headers }
      );
      if (!r.ok) return [];
      const d = await r.json();
      return (d.matches || []).map(m => ({ ...m, _competitionCode: code }));
    } catch (e) {
      return [];
    }
  }

  try {
    // Fetch WC and leagues in parallel
    const [wcMatches, ...leagueArrays] = await Promise.all([
      fetchComp('WC'),
      ...LEAGUE_CODES.map(fetchComp)
    ]);

    const leagueMatches = leagueArrays.flat();

    // Sort by date
    const sort = arr => [...arr].sort((a, b) => new Date(a.utcDate) - new Date(b.utcDate));

    // Priority: LIVE first, then SCHEDULED/TIMED by date, then FINISHED
    function prioritySort(arr) {
      const order = { 'IN_PLAY': 0, 'PAUSED': 0, 'LIVE': 0, 'SCHEDULED': 1, 'TIMED': 1, 'FINISHED': 2 };
      return [...arr].sort((a, b) => {
        const pa = order[a.status] ?? 1;
        const pb = order[b.status] ?? 1;
        if (pa !== pb) return pa - pb;
        return new Date(a.utcDate) - new Date(b.utcDate);
      });
    }

    return res.status(200).json({
      worldCup: prioritySort(wcMatches),
      leagues: prioritySort(leagueMatches),
      hasWorldCup: wcMatches.length > 0
    });

  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
