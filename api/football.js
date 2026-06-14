export default async function handler(req, res) {
  const API_KEY = 'ea172a400c534c4a97014a0658c28f09';

  try {
    const r = await fetch('https://api.football-data.org/v4/competitions/WC/matches?matchday=1', {
      headers: { 'X-Auth-Token': API_KEY }
    });
    const text = await r.text();
    return res.status(200).json({
      httpStatus: r.status,
      rawResponse: text.slice(0, 500)
    });
  } catch(e) {
    return res.status(200).json({ fetchError: e.message });
  }
}
