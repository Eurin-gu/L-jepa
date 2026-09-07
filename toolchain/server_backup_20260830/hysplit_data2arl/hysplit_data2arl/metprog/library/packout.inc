  INTERFACE
  SUBROUTINE PAKOUT(RVAR,CVAR,NX,NY,NXY,PREC,NEXP,VAR1,KSUM)
  IMPLICIT NONE
  INTEGER,   INTENT(IN)  :: nx,ny,nxy   ! dimension limits
  REAL,      INTENT(IN)  :: rvar(nx,ny) ! data array to be packed  
  CHARACTER, INTENT(OUT) :: cvar(nxy)   ! packed char*1 output array
  REAL,      INTENT(OUT) :: prec        ! precision of packed data array
  INTEGER,   INTENT(OUT) :: nexp        ! packing scaling exponent
  REAL,      INTENT(OUT) :: var1        ! value of real array at position (1,1)
  INTEGER,   INTENT(OUT) :: ksum        ! rotating checksum of packed data 
  END SUBROUTINE pakout
  END INTERFACE
