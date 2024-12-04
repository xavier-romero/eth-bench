#  zktv
Tests imported/adapted zkevm-testvectors repo.  You can run them from repo root folder:

    PROFILE=bali
    TESTS=$(ls scripted/zktv/*.json)
    for t in $TESTS; do
        echo "Running $t"
        # Use your profile here instead fork13
        python3 tool_scripted.py -p $PROFILE -f $t
    done


## Generate
To get these files you need to run this script:

    python3 toXaviFormat.py /path/to/zkevm-testvectors/tools-inputs/data/calldata/ zktv/

## Notes
- tools-input/tools-calldata/contracts --> contracts
- tools-input/tools-calldata/generate-test-vectors --> generators
- tools-input/data/calldata --> testvectors
