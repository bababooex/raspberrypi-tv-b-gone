#!/bin/bash                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                            
# === File and GPIO configuration ===                                                                                                                                                                                                       
TVBGONE_SCRIPT="tv-b-gone.py"                                                                                                                                                                                                               
JAMMER_SCRIPT="IR-jam.py"                                                                                                                                                                                                                   
IRRP_SCRIPT="irrp.py"                                                                                                                                                                                                                       
IRRP_FILE="saved_codes.json"                                                                                                                                                                                                                
IR_CONV="irconv.py"
IR_DIR="./ir_custom_files"
TX_GPIO=17
RX_GPIO=18
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
    "6" "Custom .ir file" \
    "7" "Exit" 3>&1 1>&2 2>&3)

  case "$CHOICE" in
    "1")
      whiptail --msgbox "Running TV-B-Gone script... Press Ctrl+C to return." 10 50
      python3 "$TVBGONE_SCRIPT" "$TX_GPIO"
      whiptail --msgbox "Going back to menu!" 10 50
      ;;
    "2")
      FREQ=$(whiptail --inputbox "Enter valid frequency in KHz:" 10 50 "38000" 3>&1 1>&2 2>&3)
      whiptail --msgbox "Sending square wave IR signal on $FREQ KHz... Press Ctrl+C to return." 10 50
      python3 "$JAMMER_SCRIPT" "$FREQ" "$TX_GPIO" || whiptail --msgbox "Error running Python script." 10 50
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
      if [ ! -d "$IR_DIR" ]; then
        whiptail --msgbox "Directory $IR_DIR not found!" 10 50
        continue
      fi

      IR_MENU_ITEMS=""
      for file in "$IR_DIR"/*.ir; do
        [ -e "$file" ] || continue
        filename=$(basename "$file")
        IR_MENU_ITEMS+=" $filename $filename"
      done
      SELECTED_IR=$(whiptail --title "Select .ir file" --menu "Choose a .ir file to use:" 20 60 10 $IR_MENU_ITEMS 3>&1 1>&2 2>&3)
      if [ -z "$SELECTED_IR" ]; then
        whiptail --msgbox "No file selected. Returning to menu." 10 50
        continue
      fi

      MODE=$(whiptail --title "Mode" --menu "Choose IR sending mode:" 15 60 3 \
        "1" "Dictionary attack (send all IR codes in .ir file)" \
        "2" "Single (send only one code by name)" \
        "3" "Dictionary attack by button name (e.g. Power, Mute...)" 3>&1 1>&2 2>&3)
      if [ "$MODE" = "1" ]; then
        CHAIN=$(whiptail --inputbox "Enter chain length:" 10 50 "100" 3>&1 1>&2 2>&3)
        DELAY=$(whiptail --inputbox "Enter delay between codes (ms):" 10 50 "100" 3>&1 1>&2 2>&3)
        whiptail --msgbox "Running dictionary attack using $SELECTED_IR file, set chain lenght $CHAIN and ${DELAY}ms delay" 10 60
        python3 "$IR_CONV" "$IR_DIR/$SELECTED_IR" "$CHAIN" "$TX_GPIO" "$DELAY" ||  whiptail --msgbox "Error running Python script." 10 50

      elif [ "$MODE" = "2" ]; then
        NAME_MENU_ITEMS=""
        while read -r line; do
          NAME=$(echo "$line" | cut -d: -f2- | xargs)
          NAME_MENU_ITEMS+=" $NAME $NAME"
        done < <(grep -i "^name:" "$IR_DIR/$SELECTED_IR")

        CODE_NAME=$(whiptail --title "Select IR Code" --menu "Choose code to send: (Dont use .ir file with same names!)" 20 60 10 $NAME_MENU_ITEMS 3>&1 1>&2 2>&3)
        if [ -z "$CODE_NAME" ]; then
          whiptail --msgbox "No code selected. Returning to menu." 10 50
          continue
        fi
        CHAIN=$(whiptail --inputbox "Enter chain length:" 10 50 "100" 3>&1 1>&2 2>&3)
        whiptail --msgbox "Sending code $CODE_NAME from $SELECTED_IR with chain lenght $CHAIN" 10 60
        python3 "$IR_CONV" "$IR_DIR/$SELECTED_IR" "$CODE_NAME" "$CHAIN" "$TX_GPIO" || whiptail --msgbox "Error running Python script." 10 50
      elif [ "$MODE" = "3" ]; then
       NAME_MENU_ITEMS=""
       UNIQUE_NAMES=$(grep -i "^name:" "$IR_DIR/$SELECTED_IR" | cut -d: -f2- | xargs -n1 | sort -u)
       for N in $UNIQUE_NAMES; do
          NAME_MENU_ITEMS+=" $N $N"
       done

       CODE_NAME=$(whiptail --title "Button selection" --menu "Choose button name to use:" 20 60 10 $NAME_MENU_ITEMS 3>&1 1>&2 2>&3)
       if [ -z "$CODE_NAME" ]; then
        whiptail --msgbox "No button selected. Returning to menu." 10 50
        continue
       fi
       CHAIN=$(whiptail --inputbox "Enter chain length:" 10 50 "100" 3>&1 1>&2 2>&3)
       DELAY=$(whiptail --inputbox "Enter delay between codes (ms):" 10 50 "100" 3>&1 1>&2 2>&3)
       whiptail --msgbox "Running dictionary attack with remote button $CODE_NAME from $SELECTED_IR with chain lenght $CHAIN and ${DELAY}ms delay" 10 60
       python3 "$IR_CONV" "$IR_DIR/$SELECTED_IR" "$CODE_NAME" "$CHAIN" "$TX_GPIO" "$DELAY" || whiptail --msgbox "Error running Python script." 10 50
      fi
      whiptail --msgbox "Going back to menu!" 10 50
      ;;
    "7")
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
