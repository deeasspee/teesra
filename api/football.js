export default async function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=60');
  res.setHeader('Access-Control-Allow-Origin', '*');

  const API_KEY = process.env.FOOTBALL_DATA_API_KEY;
  if (!API_KEY) {
    return res.status(500).json({ error: 'FOOTBALL_DATA_API_KEY not set', matches: [] });
  }

  const headers = { 'X-Auth-Token': API_KEY };

  async function fetchWC() {
    try {
      // First get competition info to find current matchday
      const infoRes = await fetch('https://api.football-data.org/v4/competitions/WC', { headers });
      const info = infoRes.ok ? await infoRes.json() : {};
      const currentMatchday = info.currentSeason?.currentMatchday || 1;

      console.log('WC current matchday:', currentMatchday);

      // Fetch current matchday
      const r = await fetch(
        `https://api.football-data.org/v4/competitions/WC/matches?matchday=${currentMatchday}`,
        { headers }
      );
      if (!r.ok) {
        console.error('WC matchday fetch failed:', r.status, await r.text());
        return [];
      }
      const d = await r.json();
      console.log('WC matchday', currentMatchday, 'matches:', d.matches?.length);

      if (d.matches?.length) return d.matches;

      // Fallback: try matchday-1 (just finished) and matchday+1 (upcoming)
      const [prev, next] = await Promise.all([
        fetch(`https://api.football-data.org/v4/competitions/WC/matches?matchday=${currentMatchday - 1}`, { headers }).then(r => r.ok ? r.json() : { matches: [] }),
        fetch(`https://api.football-data.org/v4/competitions/WC/matches?matchday=${currentMatchday + 1}`, { headers }).then(r => r.ok ? r.json() : { matches: [] })
      ]);

      return [...(prev.matches || []), ...(next.matches || [])];
    } catch(e) {
      console.error('WC fetch error:', e.message);
      return [];
    }
  }

  async function fetchComp(code) {
    try {
      const today = new Date();
      const from  = new Date(today); from.setDate(today.getDate() - 1);
      const to    = new Date(today); to.setDate(today.getDate() + 14);
      const fmt   = d => d.toISOString().split('T')[0];

      const r = await fetch(
        `https://api.football-data.org/v4/competitions/${code}/matches?dateFrom=${fmt(from)}&dateTo=${fmt(to)}`,
        { headers }
      );
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

  const LEAGUE_COMPS = [
    { code: 'CL',  label: 'Champions League' },
    { code: 'PL',  label: 'Premier League'   },
    { code: 'PD',  label: 'La Liga'          },
    { code: 'BL1', label: 'Bundesliga'       },
    { code: 'SA',  label: 'Serie A'          },
    { code: 'FL1', label: 'Ligue 1'          },
  ];

  try {
    const [wcRaw, ...leagueResults] = await Promise.all([
      fetchWC(),
      ...LEAGUE_COMPS.map(c => fetchComp(c.code))
    ]);

    const statusOrder = { IN_PLAY: 0, LIVE: 0, PAUSED: 0, SCHEDULED: 1, TIMED: 1, FINISHED: 2 };
    const matches = [];

    // Process WC matches
    const now = new Date();
    const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);

    const wcFiltered = wcRaw.filter(m => new Date(m.utcDate) >= yesterday);
    const wcUpcoming = wcFiltered
      .filter(m => ['SCHEDULED','TIMED','IN_PLAY','LIVE','PAUSED'].includes(m.status))
      .slice(0, 20);
    const wcFinished = wcFiltered
      .filter(m => m.status === 'FINISHED')
      .slice(-3);

    [...wcUpcoming, ...wcFinished].forEach(m => {
      const isActive = ['IN_PLAY','PAUSED','LIVE','FINISHED'].includes(m.status);
      matches.push({
        home:        m.homeTeam?.shortName || m.homeTeam?.name || 'TBD',
        away:        m.awayTeam?.shortName || m.awayTeam?.name || 'TBD',
        home_crest:  m.homeTeam?.crest || '',
        away_crest:  m.awayTeam?.crest || '',
        score_home:  isActive ? (m.score?.fullTime?.home ?? m.score?.halfTime?.home ?? null) : null,
        score_away:  isActive ? (m.score?.fullTime?.away ?? m.score?.halfTime?.away ?? null) : null,
        status:      m.status,
        minute:      m.minute || null,
        utc_date:    m.utcDate,
        competition: '🏆 FIFA World Cup 2026',
        _isWC:       true
      });
    });

    // Process league matches
    LEAGUE_COMPS.forEach((comp, i) => {
      const raw = leagueResults[i];
      const upcoming = raw
        .filter(m => ['SCHEDULED','TIMED','IN_PLAY','LIVE','PAUSED'].includes(m.status))
        .slice(0, 5);
      const finished = raw
        .filter(m => m.status === 'FINISHED')
        .slice(-3);

      [...upcoming, ...finished].forEach(m => {
        const isActive = ['IN_PLAY','PAUSED','LIVE','FINISHED'].includes(m.status);
        matches.push({
          home:        m.homeTeam?.shortName || m.homeTeam?.name || 'TBD',
          away:        m.awayTeam?.shortName || m.awayTeam?.name || 'TBD',
          home_crest:  m.homeTeam?.crest || '',
          away_crest:  m.awayTeam?.crest || '',
          score_home:  isActive ? (m.score?.fullTime?.home ?? m.score?.halfTime?.home ?? null) : null,
          score_away:  isActive ? (m.score?.fullTime?.away ?? m.score?.halfTime?.away ?? null) : null,
          status:      m.status,
          minute:      m.minute || null,
          utc_date:    m.utcDate,
          competition: comp.label,
          _isWC:       false
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

    console.log(`Football API: returning ${matches.length} matches (WC: ${matches.filter(m => m._isWC).length})`);
    return res.status(200).json({ matches });

  } catch (err) {
    console.error('Football handler error:', err);
    return res.status(500).json({ error: err.message, matches: [] });
  }
}
