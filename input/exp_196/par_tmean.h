C--
C--   Post-processing and output parameters (time-mean and variance fields) 
C--   NS2D_1 : no. of 2-d time-mean fields, incremented at post-proc. steps 
C--   NS2D_2 : no. of 2-d time-mean fields, incremented every step (fluxes)
C--   NS2D_D1: no. of 2-d daily-mean fields, incremented at post-proc. steps 
C--   NS2D_D2: no. of 2-d daily-mean fields, incremented every step (fluxes)
C--   NS3D1  : no. of 3-d time-mean model variables
C--   NS3D2  : no. of 3-d time-mean variances and covariances
C--   NS3D3  : no. of 3-d time-mean diabatic heating fields

      PARAMETER ( NS2D_1=19, NS2D_2=15, NS2D_D1=8, NS2D_D2=7,
     &            NS3D1=9, NS3D2=6, NS3D3=5 )
C--  NS2D_2 changed from 12->15 +SSRD, SLRD + SNOW - added for ACCESOM2 forcing: Natalia 03/09/2026
C--  NS2D_1 changed from 18->19 +Q0 (specific humidity) - added for ACCESOM2 forcing: Natalia 03/09/2026

      PARAMETER ( NS3D=NS3D1+NS3D2+NS3D3 )
