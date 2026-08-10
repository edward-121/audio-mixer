# audio-mixer
audio mixer where a user can input stems and create mashups \
(such as using drums from one song, and using guitar from another) \
**Current Render tier cannot split an audio clip in to the respective stems \
View @ https://audio-mixer-roan.vercel.app

To run locally: \
In the frontend folder:
- run `npm i`
- run `npm run dev`

In the backend folder: 
- run `uvicorn main:app --reload --port 8000`

And navigate to whatever url appears after `npm run dev`
