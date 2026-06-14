export default async function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const API_KEY = process.env.FOOTBALL_DATA_API_KEY;
  if (!API_KEY) {
    return res.status(500).json({ error: 'FOOTBALL_DATA_API_KEY not set', matches: [] });
  }

  const headers = { 'X-Auth-Token': API_KEY };

  async function fetchComp(code, useDateFilter) {
    try {
      // For WC: fetch current matchday without date filter first, fall back to date filter
      // For leagues: use date filter to get upcoming matches
      const today = new Date();
      const from  = new Date(today); from.setDate(today.getDate() - 1);
      const to    = new Date(today); to.setDate(today.getDate() + 14);
      const fmt   = d => d.toISOString().split('T')[0];

      const url = useDateFilter
        ? `https://api.football-data.org/v4/competitions/${code}/matches?dateFrom=${fmt(from)}&dateTo=${fmt(to)}`
        : `https://api.football-data.org/v4/competitions/${code}/matches?status=LIVE,IN_PLAY,PAUSED,SCHEDULED,TIMED`;

      const r = await fetch(url, { headers });
      if (!r.ok) {
        console.error(`${code} failed: ${r.status}`);
        return [];
      }
      const d = await r.json();
      return d.matches || [];
    } catch (e) {
      console.error(`${code} error:`, e.message);
      return [];
    }
  }

  const COMPS = [
    { code: 'WC',  label: '🏆 FIFA World Cup 2026', isWC: true,  dateFilter: false },
    { code: 'CL',  label: 'Champions League',        isWC: false, dateFilter: true  },
    { code: 'PL',  label: 'Premier League',          isWC: false, dateFilter: true  },
    { code: 'PD',  label: 'La Liga',                 isWC: false, dateFilter: true  },
    { code: 'BL1', label: 'Bundesliga',              isWC: false, dateFilter: true  },
    { code: 'SA',  label: 'Serie A',                 isWC: false, dateFilter: true  },
    { code: 'FL1', label: 'Ligue 1',                 isWC: false, dateFilter: true  },
  ];

  try {
    const results = await Promise.all(COMPS.map(c => fetchComp(c.code, c.dateFilter)));

    const statusOrder = { IN_PLAY: 0, LIVE: 0, PAUSED: 0, SCHEDULED: 1, TIMED: 1, FINISHED: 2 };

    const matches = [];

    COMPS.forEach((comp, i) => {
      const raw = results[i];

      // For WC without date filter: only show matches from today onward + recent finished (last 24h)
      const now = new Date();
      const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);

      const filtered = comp.dateFilter ? raw : raw.filter(m => {
        const matchDate = new Date(m.utcDate);
        return matchDate >= yesterday;
      });

      // Limit upcoming per competition to avoid clutter
      const upcoming = filtered
        .filter(m => ['SCHEDULED','TIMED','IN_PLAY','LIVE','PAUSED'].includes(m.status))
        .slice(0, comp.isWC ? 20 : 5);
      const finished = filtered
        .filter(m => m.status === 'FINISHED')
        .slice(-3); // last 3 finished per comp

      const toAdd = comp.isWC ? [...upcoming, ...finished] : [...upcoming, ...finished];

      toAdd.forEach(m => {
        const isActive = ['IN_PLAY','PAUSED','LIVE','FINISHED'].includes(m.status);
        matches.push({
          home:       m.homeTeam?.shortName || m.homeTeam?.name || 'TBD',
          away:       m.awayTeam?.shortName || m.awayTeam?.name || 'TBD',
          home_crest: m.homeTeam?.crest || '',
          away_crest: m.awayTeam?.crest || '',
          score_home: isActive ? (m.score?.fullTime?.home ?? m.score?.halfTime?.home ?? null) : null,
          score_away: isActive ? (m.score?.fullTime?.away ?? m.score?.halfTime?.away ?? null) : null,
          status:     m.status,
          minute:     m.minute || null,
          utc_date:   m.utcDate,
          competition: comp.label,
          _isWC:      comp.isWC
        });
      });
    });

    // Sort: LIVE first, then by date
    matches.sort((a, b) => {
      const pa = statusOrder[a.status] ?? 1;
      const pb = statusOrder[b.status] ?? 1;
      if (pa !== pb) return pa - pb;
      return new Date(a.utc_date) - new Date(b.utc_date);
    });

    console.log(`Football API: returning ${matches.length} matches (WC: ${matches.filter(m=>m._isWC).length})`);
    return res.status(200).json({ matches });

  } catch (err) {
    console.error('Football handler error:', err);
    return res.status(500).json({ error: err.message, matches: [] });
  }
}
