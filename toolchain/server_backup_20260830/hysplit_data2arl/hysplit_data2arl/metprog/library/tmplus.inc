INTERFACE
   SUBROUTINE TMPLUS(IY,IM,ID,IH,IC)
      IMPLICIT NONE
      INTEGER,  INTENT(INOUT) :: iy,im,id      ! current date
      INTEGER,  INTENT(INOUT) :: ih            ! current hour
      INTEGER,  INTENT(IN)    :: ic            ! increment in hours
   END SUBROUTINE tmplus
END INTERFACE
