# Submission checklist

- [ ] GitHub repo (public) with README
- [ ] Actions: green `test` and `docker-build`; green deploy jobs (screenshot)
- [ ] Frontend URL showing the dashboard (screenshot)
- [ ] Backend URL `/docs` and `/health` (screenshot)
- [ ] HIGH-risk result and AI diagnosis in the dashboard (screenshot)
- [ ] Rollback workflow run (screenshot)
- [ ] 2-minute demo video

## Claims you may make only when true
- "Deployed on Elastic Beanstalk with Docker": after both deploy jobs are green and both URLs open.
- "Live CloudWatch metrics": after /metrics/live returns real values.
- "Rollback via pipeline": after you ran the Rollback workflow successfully.
