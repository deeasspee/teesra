export default async function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const API_KEY = process.env.FOOTBALL_DATA_API_KEY;
  if (!API_KEY) {
    return res.status(500).json({ error: 'FOOTBALL_DATA_API_KEY not set', matches: [] });
  }

  const headers = { 'X-Auth-Token': API_KEY };

  // Wide window: yesterday to 10 days ahead — ensures upcoming matches always show
  const today = new Date();
  const from  = new Date(today); from.setDate(today.getDate() - 1);
  const to    = new Date(today); to.setDate(today.getDate() + 10);
  const fmt   = d => d.toISOString().split('T')[0];
  const range = `dateFrom=${fmt(from)}&dateTo=${fmt(to)}`;

  // All competitions available on free tier
  const COMPS = [
    { code: 'WC',  label: '🏆 FIFA World Cup 2026', isWC: true  },
    { code: 'CL',  label: 'Champions League',        isWC: false },
    { code: 'PL',  label: 'Premier League',          isWC: false },
    { code: 'PD',  label: 'La Liga',                 isWC: false },
    { code: 'BL1', label: 'Bundesliga',              isWC: false },
    { code: 'SA',  label: 'Serie A',                 isWC: false },
    { code: 'FL1', label: 'Ligue 1',                 isWC: false },
  ];

  async function fetchComp(code) {
    try {
      const r = await fetch(
        `https://api.football-data.org/v4/competitions/${code}/matches?${range}`,
        { headers }
      );
      if (!r.ok) return [];
      const d = await r.json();
      return d.matches || [];
    } catch (e) {
      return [];
    }
  }

  try {
    const results = await Promise.all(COMPS.map(c => fetchComp(c.code)));

    // Status priority: LIVE > SCHEDULED/TIMED > FINISHED
    const statusOrder = { IN_PLAY: 0, LIVE: 0, PAUSED: 0, SCHEDULED: 1, TIMED: 1, FINISHED: 2 };

    function sortMatches(arr) {
      return arr.sort((a, b) => {
        const pa = statusOrder[a.status] ?? 1;
        const pb = statusOrder[b.status] ?? 1;
        if (pa !== pb) return pa - pb;
        return new Date(a.utcDate) - new Date(b.utcDate);
      });
    }

    const matches = [];

    COMPS.forEach((comp, i) => {
      const raw = results[i];
      raw.forEach(m => {
        matches.push({
          home:       m.homeTeam?.shortName || m.homeTeam?.name || '?',
          away:       m.awayTeam?.shortName || m.awayTeam?.name || '?',
          home_crest: m.homeTeam?.crest || '',
          away_crest: m.awayTeam?.crest || '',
          score_home: ['IN_PLAY','PAUSED','LIVE','FINISHED'].includes(m.status)
                        ? (m.score?.fullTime?.home ?? m.score?.halfTime?.home ?? null)
                        : null,
          score_away: ['IN_PLAY','PAUSED','LIVE','FINISHED'].includes(m.status)
                        ? (m.score?.fullTime?.away ?? m.score?.halfTime?.away ?? null)
                        : null,
          status:     m.status,
          minute:     m.minute || null,
          utc_date:   m.utcDate,
          competition: comp.label,
          _isWC:      comp.isWC
        });
      });
    });

    sortMatches(matches);

    return res.status(200).json({ matches });

  } catch (err) {
    return res.status(500).json({ error: err.message, matches: [] });
  }
}
