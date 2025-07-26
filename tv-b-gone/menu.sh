#!/bin/bash
#Script uses whiptail to create "user friendly" interface

# === File and GPIO configuration ===
TVBGONE_SCRIPT="tv-b-gone.py"
JAMMER_SCRIPT="IR-jam.py"
IRRP_SCRIPT="irrp.py"
IRRP_FILE="saved_codes.json"
TX_GPIO=17 #Same pin as tv-b-gone python file
RX_GPIO=18 #For IR reception
# ===================================

whiptail --msgbox "Hello!\nActivating pigpiod!" 10 50
sudo pigpiod

while true; do
  CHOICE=$(whiptail --title "TV-B-GONE Control Panel" --menu "Choose an option:" 20 60 10 \
    "1" "Send TV-B-Gone codes" \
    "2" "IR Jammer (oscillator)" \
    "3" "Record new IR code (irrp)" \
    "4" "Play IR code (irrp)" \
    "5" "Delete IR code from file (irrp)" \
    "6" "Exit" 3>&1 1>&2 2>&3)

  case "$CHOICE" in
    "1")
      whiptail --msgbox "Running TV-B-Gone script... Press Ctrl+C to return." 10 50
      python3 "$TVBGONE_SCRIPT"
      whiptail --msgbox "Going back to menu!" 10 50
      ;;
    "2")
      whiptail --msgbox "Sending 38kHz blank signal... Press Ctrl+C to return." 10 50
      python3 "$JAMMER_SCRIPT"
      whiptail --msgbox "Going back to menu!" 10 50
      ;;

    "3")
       CODE_NAME=$(whiptail --inputbox "Enter a name for the IR code (use letters, numbers, underscores only):" 10 60 3>&1 1>&2 2>&3)
      if [[ ! "$CODE_NAME" =~ ^[a-zA-Z0-9_]+$ ]]; then
        whiptail --msgbox "Bad character used!\nGoing back to menu!" 10 50
        continue
      fi
      if [ -n "$CODE_NAME" ]; then
      FREQ=$(whiptail --inputbox "Enter record frequency in kHz (default is 38):" 10 50 "38" 3>&1 1>&2 2>&3)
      if [[ "$FREQ" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        python3 "$IRRP_SCRIPT" -r -g $RX_GPIO -f "$IRRP_FILE" --freq "$FREQ" "$CODE_NAME"
      else
        python3 "$IRRP_SCRIPT" -r -g $RX_GPIO -f "$IRRP_FILE" "$CODE_NAME"
      fi
       else
       whiptail --msgbox "Going back to menu!" 10 50
     fi
     ;;
    "4")
      if [ ! -s "$IRRP_FILE" ] || [ "$(jq -r 'keys | length' "$IRRP_FILE")" -eq 0 ]; then
        whiptail --msgbox "No IR codes found in $IRRP_FILE" 10 50
        continue
      fi
      MENU_ITEMS=""
      while IFS= read -r name; do
        MENU_ITEMS+=" $name $name"
      done < <(jq -r 'keys[]' "$IRRP_FILE")

      CODE_TO_PLAY=$(whiptail --title "Play IR Code" --menu "Choose a code to play:" 20 60 10 $MENU_ITEMS 3>&1 1>&2 2>&3)
      if [ -n "$CODE_TO_PLAY" ]; then
        FREQ=$(whiptail --inputbox "Enter playback frequency in kHz (default is 38):" 10 50 "38" 3>&1 1>&2 2>&3)
        if [[ "$FREQ" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
          python3 "$IRRP_SCRIPT" -p -g $TX_GPIO -f "$IRRP_FILE" --freq "$FREQ" "$CODE_TO_PLAY"
        else
          python3 "$IRRP_SCRIPT" -p -g $TX_GPIO -f "$IRRP_FILE" "$CODE_TO_PLAY"
        fi
          else
        whiptail --msgbox "Going back to menu!" 10 50
      fi
      ;;
    "5")
      if [ ! -s "$IRRP_FILE" ] || [ "$(jq -r 'keys | length' "$IRRP_FILE")" -eq 0 ]; then
        whiptail --msgbox "No IR codes found in $IRRP_FILE" 10 50
        continue
      fi

      MENU_ITEMS=""
      while IFS= read -r name; do
        MENU_ITEMS+=" $name $name"
      done < <(jq -r 'keys[]' "$IRRP_FILE")

      CODE_TO_DELETE=$(whiptail --title "Delete IR Code" --menu "Select a code to delete:" 20 60 10 $MENU_ITEMS 3>&1 1>&2 2>&3)
      if [ -n "$CODE_TO_DELETE" ]; then
        whiptail --yesno "Are you sure you want to delete '$CODE_TO_DELETE'?" 10 50
        if [ $? -eq 0 ]; then
          jq "del(.\"$CODE_TO_DELETE\")" "$IRRP_FILE" > /tmp/ir_tmp.json && mv /tmp/ir_tmp.json "$IRRP_FILE"
          whiptail --msgbox "Code '$CODE_TO_DELETE' deleted." 8 40
        fi
          else
         whiptail --msgbox "Going back to menu!" 10 50
      fi
      ;;
    "6")
      whiptail --msgbox "Deactivating pigpiod!\nGood bye!" 10 50
      sudo pigpiod kill
      break
      ;;
    *)
      whiptail --msgbox "Deactivating pigpiod!\nGood bye!" 10 50
      sudo pigpiod kill
      break
      ;;
  esac
done


