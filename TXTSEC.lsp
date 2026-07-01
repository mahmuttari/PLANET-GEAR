;;; ===========================================================================
;;; TXTSEC.LSP  -  Text Icerigine Gore Nesne Secim Filtresi
;;; ---------------------------------------------------------------------------
;;; Komut : TXTSEC
;;;
;;; Amac  : Ekrandaki (aktif uzaydaki) TEXT / MTEXT nesnelerini, iceriklerindeki
;;;         metne gore filtreleyip secer. Eslesen nesneler grip'li (secili) hale
;;;         gelir; ardindan MOVE, COPY, ERASE vb. ile kullanabilirsiniz.
;;;
;;; Kullanim:
;;;   1. Aranacak metni yazin  (veya bos birakip ENTER'a basip ornek bir
;;;      text secerek o textin icerigini arama metni olarak kullanabilirsiniz).
;;;   2. Eslesme turu:  [Icerir / Tam / Kalip]
;;;        Icerir : metni ICINDE barindiran texler       (varsayilan)
;;;        Tam    : metnin TAMAMI birebir ayni olanlar
;;;        Kalip  : joker karakterli arama ( *  ?  #  vb. )  ornek: PLAN*
;;;   3. Buyuk/kucuk harf duyarli olsun mu?  [Evet / Hayir]  (varsayilan Hayir)
;;; ===========================================================================

;;; --- MTEXT formatlama kodlarini temizle ------------------------------------
(defun txtsec:clean (s / r)
  (setq r s)
  (while (vl-string-search "\\P" r) (setq r (vl-string-subst " " "\\P" r)))
  (while (vl-string-search "{"   r) (setq r (vl-string-subst ""  "{"   r)))
  (while (vl-string-search "}"   r) (setq r (vl-string-subst ""  "}"   r)))
  r
)

;;; --- Bir text/mtext nesnesinin duz metnini al ------------------------------
(defun txtsec:content (ename / d typ)
  (setq d   (entget ename)
        typ (cdr (assoc 0 d)))
  (cond
    ((= typ "TEXT")  (cdr (assoc 1 d)))
    ((= typ "MTEXT") (txtsec:clean (vla-get-TextString (vlax-ename->vla-object ename))))
    (T "")
  )
)

;;; ===========================================================================
(defun c:TXTSEC ( / *error* base pat mode cs ans ent
                    i n val patM valM res match )

  (defun *error* (msg)
    (if (and msg (not (member msg '("Function cancelled" "quit / exit abort"))))
      (princ (strcat "\nHata: " msg)))
    (princ)
  )

  (vl-load-com)
  (princ "\n=== Text Icerigine Gore Nesne Secimi ===")

  ;; --- Aktif uzaydaki tum TEXT / MTEXT nesnelerini topla --------------------
  (setq base (ssget "_X" (list '(0 . "TEXT,MTEXT")
                               (cons 410 (getvar "CTAB")))))
  (if (null base)
    (progn (princ "\nAktif uzayda hic TEXT/MTEXT bulunamadi.") (exit)))

  ;; --- Aranacak metni al ----------------------------------------------------
  (setq pat (getstring T "\nAranacak metin (bos birakip ENTER = ornek text sec): "))
  (if (= pat "")
    (progn
      (while (null ent)
        (setq ent (car (entsel "\nOrnek TEXT/MTEXT secin: ")))
        (if (and ent (not (member (cdr (assoc 0 (entget ent))) '("TEXT" "MTEXT"))))
          (progn (princ "\n  >> Bu bir TEXT/MTEXT degil.") (setq ent nil))))
      (setq pat (txtsec:content ent))
      (princ (strcat "\nAranan metin: \"" pat "\""))))

  ;; --- Eslesme turu ---------------------------------------------------------
  (initget "Icerir Tam Kalip")
  (setq mode (cond ((getkword "\nEslesme turu [Icerir/Tam/Kalip] <Icerir>: "))
                   ("Icerir")))

  ;; --- Buyuk/kucuk harf duyarliligi -----------------------------------------
  (initget "Evet Hayir")
  (setq cs (= "Evet" (cond ((getkword "\nBuyuk/kucuk harf duyarli? [Evet/Hayir] <Hayir>: "))
                           ("Hayir"))))

  ;; --- Filtreleme -----------------------------------------------------------
  (setq patM (if cs pat (strcase pat))
        res  (ssadd)
        i    0
        n    (sslength base))
  (while (< i n)
    (setq ent  (ssname base i)
          val  (txtsec:content ent)
          valM (if cs val (strcase val)))
    (setq match
      (cond
        ((= mode "Tam")    (= valM patM))
        ((= mode "Kalip")  (wcmatch valM patM))
        (T                 (and (/= patM "") (vl-string-search patM valM)))  ; Icerir
      ))
    (if match (ssadd ent res))
    (setq i (1+ i)))

  ;; --- Sonuc ----------------------------------------------------------------
  (if (> (sslength res) 0)
    (progn
      (sssetfirst nil res)     ; nesneleri secili + grip'li yap
      (princ (strcat "\n>> " (itoa (sslength res)) " nesne secildi ("
                     (itoa n) " text tarandi)."))
    )
    (princ "\n>> Eslesen text bulunamadi.")
  )
  (princ)
)

(princ "\nTXTSEC.LSP yuklendi. Calistirmak icin komut satirina  TXTSEC  yazin.")
(princ)
